from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.alerts.service import evaluate_alerts
from app.api.schemas import (
    AIInterpretationResponse,
    AlertCreate,
    AlertDeliveryResponse,
    AlertResponse,
    AlertUpdate,
    ChangeResponse,
    DailyReportResponse,
    DataSourceResponse,
    EventResponse,
    HistoryPoint,
    InstrumentCreate,
    InstrumentResponse,
    InvestmentThesisResponse,
    InvestmentThesisUpsert,
    JobResponse,
    NewsResponse,
    OwnershipResponse,
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistResponse,
    WatchlistUpdate,
)
from app.config import get_settings
from app.db.models import (
    AIInterpretation,
    Alert,
    AlertDelivery,
    Change,
    DailyReport,
    DataSource,
    EstimateSnapshot,
    Event,
    FlowDaily,
    FundamentalSnapshot,
    Instrument,
    InstrumentAlias,
    InvestmentThesis,
    JobRun,
    NewsInstrument,
    NewsItem,
    OwnershipSnapshot,
    PriceDaily,
    Watchlist,
    WatchlistItem,
)
from app.db.session import get_db
from app.instruments.registry import lookup_sec_company, lookup_twse_company
from app.interpretation.service import generate_interpretation
from app.jobs.pipeline import run_price_history_backfill_sync
from app.news.service import enrich_news_item
from app.reports.ai_daily import generate_ai_daily_brief
from app.reports.daily import generate_daily_reports

router = APIRouter()


def _news_response(item: NewsItem) -> NewsResponse:
    return NewsResponse(
        id=item.id,
        headline=item.headline,
        published_at=item.published_at,
        source_name=item.source_name,
        source_url=item.source_url,
        category=item.category,
        importance_score=item.importance_score,
        is_material=item.is_material,
        summary=item.summary,
        article_excerpt=item.article_text[:800] if item.article_text else None,
        content_status=item.content_status,
        cluster_key=item.cluster_key,
        ai_confidence=item.ai_confidence,
    )


@router.get("/data-sources", response_model=list[DataSourceResponse])
def list_data_sources(
    market: str | None = Query(None, pattern="^(TW|US)$"),
    domain: str | None = None,
    db: Session = Depends(get_db),
):
    """Expose source coverage, including intentionally disabled future feeds."""
    rows = db.scalars(select(DataSource).order_by(DataSource.code))
    result = []
    for source in rows:
        metadata = source.metadata_ or {}
        markets = metadata.get("markets", [])
        domains = metadata.get("domains", [])
        if market and market not in markets:
            continue
        if domain and domain not in domains:
            continue
        result.append(
            DataSourceResponse(
                code=source.code,
                name=source.name,
                source_type=source.source_type,
                confidence=source.confidence,
                is_enabled=source.is_enabled,
                markets=markets,
                domains=domains,
                cadence=metadata.get("cadence"),
                access=metadata.get("access"),
                url=metadata.get("url"),
            )
        )
    return result


def _effective_at(db: Session, change: Change) -> datetime | None:
    """Return the source-data timestamp rather than the pipeline detection time."""
    if change.current_snapshot_id is None:
        return None
    model_and_field = {
        "price_daily": (PriceDaily, "trading_date"),
        "flow_daily": (FlowDaily, "trading_date"),
        "estimate_snapshots": (EstimateSnapshot, "observed_at"),
        "fundamentals": (FundamentalSnapshot, "observed_at"),
        "ownership_snapshots": (OwnershipSnapshot, "snapshot_date"),
        "events": (Event, "event_date"),
        "news_items": (NewsItem, "published_at"),
    }.get(change.current_snapshot_type or "")
    if model_and_field is None:
        return None
    model, field = model_and_field
    snapshot = db.get(model, change.current_snapshot_id)
    if snapshot is None or getattr(snapshot, field) is None:
        return None
    value = getattr(snapshot, field)
    return (
        value if isinstance(value, datetime) else datetime.combine(value, datetime.min.time(), UTC)
    )


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(select(1))
    return {"status": "ok"}


@router.get("/changes", response_model=list[ChangeResponse])
def list_changes(
    min_score: float = Query(50, ge=0, le=100),
    market: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    hours: int = Query(24, ge=1, le=8760),
    limit: int = Query(100, ge=1, le=200),
    watchlist_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    query = (
        select(Change, Instrument, DataSource)
        .join(Instrument, Instrument.id == Change.instrument_id)
        .outerjoin(DataSource, DataSource.id == Change.source_id)
        .where(
            Change.total_score >= min_score,
            Change.detected_at >= datetime.now(UTC) - timedelta(hours=hours),
            Instrument.id.in_(select(WatchlistItem.instrument_id).distinct()),
        )
        .order_by(desc(Change.total_score), desc(Change.detected_at))
        .limit(limit)
    )
    if market:
        query = query.where(Instrument.market == market.upper())
    if category:
        query = query.where(Change.category == category)
    if severity:
        query = query.where(Change.severity == severity)
    if watchlist_id:
        query = query.join(
            WatchlistItem, WatchlistItem.instrument_id == Change.instrument_id
        ).where(WatchlistItem.watchlist_id == watchlist_id)
    return [
        ChangeResponse(
            id=change.id,
            symbol=instrument.symbol,
            company_name=instrument.company_name,
            market=instrument.market,
            category=change.category,
            metric=change.metric,
            period=change.period,
            lookback=change.lookback,
            previous_value=change.previous_value,
            current_value=change.current_value,
            absolute_change=change.absolute_change,
            percentage_change=change.percentage_change,
            direction=change.direction,
            severity=change.severity,
            total_score=change.total_score,
            source_code=source.code if source else None,
            source_name=source.name if source else None,
            source_confidence=source.confidence if source else None,
            previous_snapshot_type=change.previous_snapshot_type,
            current_snapshot_type=change.current_snapshot_type,
            headline=change.metadata_.get("headline") if change.metadata_ else None,
            event_title=change.metadata_.get("title") if change.metadata_ else None,
            effective_at=_effective_at(db, change),
            detected_at=change.detected_at,
        )
        for change, instrument, source in db.execute(query)
    ]


@router.get("/changes/{change_id}", response_model=ChangeResponse)
def get_change(change_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        select(Change, Instrument, DataSource)
        .join(Instrument, Instrument.id == Change.instrument_id)
        .outerjoin(DataSource, DataSource.id == Change.source_id)
        .where(Change.id == change_id)
    ).first()
    if not row:
        raise HTTPException(404, "Change not found")
    change, instrument, source = row
    return ChangeResponse(
        id=change.id,
        symbol=instrument.symbol,
        company_name=instrument.company_name,
        market=instrument.market,
        category=change.category,
        metric=change.metric,
        period=change.period,
        lookback=change.lookback,
        previous_value=change.previous_value,
        current_value=change.current_value,
        absolute_change=change.absolute_change,
        percentage_change=change.percentage_change,
        direction=change.direction,
        severity=change.severity,
        total_score=change.total_score,
        source_code=source.code if source else None,
        source_name=source.name if source else None,
        source_confidence=source.confidence if source else None,
        previous_snapshot_type=change.previous_snapshot_type,
        current_snapshot_type=change.current_snapshot_type,
        headline=change.metadata_.get("headline") if change.metadata_ else None,
        event_title=change.metadata_.get("title") if change.metadata_ else None,
        effective_at=_effective_at(db, change),
        detected_at=change.detected_at,
    )


@router.get("/companies", response_model=list[InstrumentResponse])
def list_companies(db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(Instrument).where(Instrument.is_active.is_(True)).order_by(Instrument.symbol)
        )
    )


@router.post("/companies", response_model=InstrumentResponse, status_code=201)
def create_company(payload: InstrumentCreate, db: Session = Depends(get_db)):
    symbol = payload.symbol.strip().upper()
    if not symbol:
        raise HTTPException(422, "Symbol must not be blank")
    if db.scalar(
        select(Instrument).where(Instrument.market == payload.market, Instrument.symbol == symbol)
    ):
        raise HTTPException(409, "Company already exists")

    official_profile = lookup_twse_company(symbol) if payload.market == "TW" else None
    company_name = (payload.company_name or "").strip() or (
        official_profile[0] if official_profile else symbol
    )
    exchange = (payload.exchange or "").strip().upper() or (
        official_profile[1] if official_profile else None
    )
    instrument = Instrument(
        symbol=symbol,
        market=payload.market,
        exchange=exchange,
        company_name=company_name,
        currency="TWD" if payload.market == "TW" else "USD",
    )
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    return instrument


@router.get("/companies/search", response_model=list[InstrumentResponse])
def search_companies(
    q: str = Query(min_length=1, max_length=255),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    pattern = f"%{q.strip().lower()}%"
    rows = list(
        db.scalars(
            select(Instrument)
            .outerjoin(InstrumentAlias, InstrumentAlias.instrument_id == Instrument.id)
            .where(
                Instrument.is_active.is_(True),
                or_(
                    func.lower(Instrument.symbol).like(pattern),
                    func.lower(Instrument.company_name).like(pattern),
                    func.lower(InstrumentAlias.alias).like(pattern),
                ),
            )
            .distinct()
            .order_by(Instrument.symbol)
            .limit(limit)
        )
    )
    query = q.strip().upper()
    is_tw_symbol = query.isdigit() and len(query) in (4, 6)
    is_us_symbol = query.isalpha() and 1 <= len(query) <= 5
    if not (is_tw_symbol or is_us_symbol):
        return rows

    exact_match = next((row for row in rows if row.symbol.upper() == query), None)
    if exact_match:
        return [exact_match]

    official_profile = lookup_twse_company(query) if is_tw_symbol else None
    if official_profile:
        company_name, exchange = official_profile
        market = "TW"
        currency = "TWD"
    else:
        company_name = lookup_sec_company(query.upper(), get_settings().sec_user_agent)
        if not company_name:
            return rows
        exchange = None
        market = "US"
        currency = "USD"
    instrument = Instrument(
        symbol=query,
        market=market,
        exchange=exchange,
        company_name=company_name,
        currency=currency,
    )
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    return [instrument, *rows][:limit]


@router.get("/companies/{symbol}", response_model=InstrumentResponse)
def get_company(symbol: str, db: Session = Depends(get_db)):
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if not instrument:
        raise HTTPException(404, "Company not found")
    return instrument


@router.get("/companies/{symbol}/changes", response_model=list[ChangeResponse])
def company_changes(symbol: str, db: Session = Depends(get_db)):
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if not instrument:
        raise HTTPException(404, "Company not found")
    changes = db.execute(
        select(Change, DataSource)
        .outerjoin(DataSource, DataSource.id == Change.source_id)
        .where(Change.instrument_id == instrument.id)
        .order_by(desc(Change.detected_at))
        .limit(200)
    )
    return [
        ChangeResponse(
            id=change.id,
            symbol=instrument.symbol,
            company_name=instrument.company_name,
            market=instrument.market,
            category=change.category,
            metric=change.metric,
            period=change.period,
            lookback=change.lookback,
            previous_value=change.previous_value,
            current_value=change.current_value,
            absolute_change=change.absolute_change,
            percentage_change=change.percentage_change,
            direction=change.direction,
            severity=change.severity,
            total_score=change.total_score,
            source_code=source.code if source else None,
            source_name=source.name if source else None,
            source_confidence=source.confidence if source else None,
            previous_snapshot_type=change.previous_snapshot_type,
            current_snapshot_type=change.current_snapshot_type,
            headline=change.metadata_.get("headline") if change.metadata_ else None,
            event_title=change.metadata_.get("title") if change.metadata_ else None,
            effective_at=_effective_at(db, change),
            detected_at=change.detected_at,
        )
        for change, source in changes
    ]


@router.get("/companies/{symbol}/history", response_model=list[HistoryPoint])
def company_history(symbol: str, db: Session = Depends(get_db)):
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if not instrument:
        raise HTTPException(404, "Company not found")
    prices = db.scalars(
        select(PriceDaily)
        .where(PriceDaily.instrument_id == instrument.id)
        .order_by(PriceDaily.trading_date.desc())
        .limit(120)
    )
    estimates = db.scalars(
        select(EstimateSnapshot)
        .where(EstimateSnapshot.instrument_id == instrument.id)
        .order_by(EstimateSnapshot.observed_at.desc())
        .limit(120)
    )
    flows = db.scalars(
        select(FlowDaily)
        .where(FlowDaily.instrument_id == instrument.id)
        .order_by(FlowDaily.trading_date.desc())
        .limit(120)
    )
    fundamentals = db.scalars(
        select(FundamentalSnapshot)
        .where(FundamentalSnapshot.instrument_id == instrument.id)
        .order_by(FundamentalSnapshot.observed_at.desc())
        .limit(120)
    )
    points = [
        HistoryPoint(
            metric="close",
            observed_at=datetime.combine(row.trading_date, datetime.min.time(), tzinfo=UTC),
            value=row.close,
            unit=instrument.currency,
        )
        for row in prices
    ]
    points.extend(
        HistoryPoint(metric=row.metric, observed_at=row.observed_at, value=row.value, unit=row.unit)
        for row in estimates
    )
    points.extend(
        HistoryPoint(
            metric=f"flow:{row.flow_type}",
            observed_at=datetime.combine(row.trading_date, datetime.min.time(), tzinfo=UTC),
            value=row.net_volume,
            unit=row.unit,
        )
        for row in flows
    )
    points.extend(
        HistoryPoint(metric=row.metric, observed_at=row.observed_at, value=row.value, unit=row.unit)
        for row in fundamentals
    )
    return sorted(points, key=lambda point: point.observed_at)


@router.get("/events", response_model=list[EventResponse])
def list_events(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    today = datetime.now(UTC).date()
    rows = db.execute(
        select(Event, Instrument)
        .outerjoin(Instrument, Instrument.id == Event.instrument_id)
        .where(Event.event_date >= today, Event.event_date <= today + timedelta(days=days))
        .order_by(Event.event_date, Event.title)
    )
    return [
        EventResponse(
            id=event.id,
            symbol=instrument.symbol if instrument else None,
            event_type=event.event_type,
            title=event.title,
            event_date=event.event_date,
            source_url=event.source_url,
            status=event.status,
        )
        for event, instrument in rows
    ]


@router.get("/reports/daily", response_model=list[DailyReportResponse])
def list_daily_reports(
    report_type: str | None = None,
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    query = select(DailyReport).order_by(
        desc(DailyReport.report_date), desc(DailyReport.created_at)
    )
    if report_type:
        query = query.where(DailyReport.report_type == report_type)
    return list(db.scalars(query.limit(limit)))


@router.post("/reports/daily/generate", response_model=list[DailyReportResponse])
def generate_reports(db: Session = Depends(get_db)):
    reports = generate_daily_reports(db)
    db.commit()
    return reports


@router.post("/reports/daily/ai-generate", response_model=DailyReportResponse, status_code=201)
def generate_ai_report(db: Session = Depends(get_db)):
    report = generate_ai_daily_brief(db)
    db.commit()
    db.refresh(report)
    return report


@router.get("/companies/{symbol}/events", response_model=list[EventResponse])
def company_events(symbol: str, db: Session = Depends(get_db)):
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if not instrument:
        raise HTTPException(404, "Company not found")
    events = db.scalars(
        select(Event).where(Event.instrument_id == instrument.id).order_by(Event.event_date)
    ).yield_per(100)
    return [
        EventResponse(
            id=event.id,
            symbol=instrument.symbol,
            event_type=event.event_type,
            title=event.title,
            event_date=event.event_date,
            source_url=event.source_url,
            status=event.status,
        )
        for event in events
    ]


@router.get("/news", response_model=list[NewsResponse])
def list_news(
    days: int = Query(7, ge=1, le=365),
    category: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = select(NewsItem).where(
        NewsItem.published_at >= datetime.now(UTC) - timedelta(days=days)
    )
    if category:
        query = query.where(NewsItem.category == category)
    return [
        _news_response(item)
        for item in db.scalars(query.order_by(desc(NewsItem.published_at)).limit(limit))
    ]


@router.get("/companies/{symbol}/news", response_model=list[NewsResponse])
def company_news(
    symbol: str,
    days: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
):
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if not instrument:
        raise HTTPException(404, "Company not found")
    rows = db.execute(
        select(NewsItem)
        .join(NewsInstrument, NewsInstrument.news_item_id == NewsItem.id)
        .where(
            NewsInstrument.instrument_id == instrument.id,
            NewsItem.published_at >= datetime.now(UTC) - timedelta(days=days),
        )
        .order_by(desc(NewsItem.published_at))
        .limit(100)
    )
    return [_news_response(item) for item in rows.scalars()]


@router.post("/news/{news_id}/enrich", response_model=NewsResponse)
async def enrich_news(news_id: int, db: Session = Depends(get_db)):
    item = db.get(NewsItem, news_id)
    if not item:
        raise HTTPException(404, "News item not found")
    await enrich_news_item(item)
    db.commit()
    db.refresh(item)
    return _news_response(item)


@router.get("/companies/{symbol}/ownership", response_model=list[OwnershipResponse])
def company_ownership(symbol: str, db: Session = Depends(get_db)):
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if not instrument:
        raise HTTPException(404, "Company not found")
    rows = db.scalars(
        select(OwnershipSnapshot)
        .where(OwnershipSnapshot.instrument_id == instrument.id)
        .order_by(desc(OwnershipSnapshot.snapshot_date))
        .limit(200)
    )
    return [
        OwnershipResponse(
            id=row.id,
            symbol=instrument.symbol,
            snapshot_date=row.snapshot_date,
            holder_bucket=row.holder_bucket,
            holder_count=row.holder_count,
            share_count=row.share_count,
            ownership_pct=row.ownership_pct,
        )
        for row in rows
    ]


@router.get("/companies/{symbol}/interpretations", response_model=list[AIInterpretationResponse])
def company_interpretations(symbol: str, db: Session = Depends(get_db)):
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if not instrument:
        raise HTTPException(404, "Company not found")
    rows = db.scalars(
        select(AIInterpretation)
        .where(AIInterpretation.instrument_id == instrument.id)
        .order_by(desc(AIInterpretation.generated_at))
        .limit(100)
    )
    return [
        AIInterpretationResponse(
            id=row.id,
            symbol=instrument.symbol,
            interpretation_type=row.interpretation_type,
            summary=row.summary,
            why_it_matters=row.why_it_matters,
            supporting_signals=row.supporting_signals,
            contradictions=row.contradictions,
            watch_next=row.watch_next,
            thesis_impact=row.thesis_impact,
            evidence=row.evidence,
            confidence=row.confidence,
            data_gaps=row.data_gaps,
            model_provider=row.model_provider,
            model_name=row.model_name,
            prompt_version=row.prompt_version,
            generated_at=row.generated_at,
        )
        for row in rows
    ]


@router.post(
    "/companies/{symbol}/interpretations/generate",
    response_model=AIInterpretationResponse,
    status_code=201,
)
def generate_company_interpretation(symbol: str, db: Session = Depends(get_db)):
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if not instrument:
        raise HTTPException(404, "Company not found")
    interpretation = generate_interpretation(db, instrument)
    if not interpretation:
        raise HTTPException(409, "No material changes available for interpretation")
    db.commit()
    return AIInterpretationResponse(
        id=interpretation.id,
        symbol=instrument.symbol,
        interpretation_type=interpretation.interpretation_type,
        summary=interpretation.summary,
        why_it_matters=interpretation.why_it_matters,
        supporting_signals=interpretation.supporting_signals,
        contradictions=interpretation.contradictions,
        watch_next=interpretation.watch_next,
        thesis_impact=interpretation.thesis_impact,
        evidence=interpretation.evidence,
        confidence=interpretation.confidence,
        data_gaps=interpretation.data_gaps,
        model_provider=interpretation.model_provider,
        model_name=interpretation.model_name,
        prompt_version=interpretation.prompt_version,
        generated_at=interpretation.generated_at,
    )


@router.get("/companies/{symbol}/thesis", response_model=InvestmentThesisResponse)
def get_company_thesis(symbol: str, db: Session = Depends(get_db)):
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if not instrument:
        raise HTTPException(404, "Company not found")
    thesis = db.scalar(
        select(InvestmentThesis).where(InvestmentThesis.instrument_id == instrument.id)
    )
    if not thesis:
        raise HTTPException(404, "Investment thesis not found")
    return InvestmentThesisResponse(
        symbol=instrument.symbol,
        **{
            key: getattr(thesis, key)
            for key in (
                "id",
                "thesis",
                "key_kpis",
                "catalysts",
                "risks",
                "invalidation_conditions",
                "created_at",
                "updated_at",
            )
        },
    )


@router.put("/companies/{symbol}/thesis", response_model=InvestmentThesisResponse)
def upsert_company_thesis(
    symbol: str, payload: InvestmentThesisUpsert, db: Session = Depends(get_db)
):
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if not instrument:
        raise HTTPException(404, "Company not found")
    thesis = db.scalar(
        select(InvestmentThesis).where(InvestmentThesis.instrument_id == instrument.id)
    )
    if not thesis:
        thesis = InvestmentThesis(instrument_id=instrument.id, **payload.model_dump())
        db.add(thesis)
    else:
        for key, value in payload.model_dump().items():
            setattr(thesis, key, value)
    db.commit()
    db.refresh(thesis)
    return InvestmentThesisResponse(
        symbol=instrument.symbol,
        **{
            key: getattr(thesis, key)
            for key in (
                "id",
                "thesis",
                "key_kpis",
                "catalysts",
                "risks",
                "invalidation_conditions",
                "created_at",
                "updated_at",
            )
        },
    )


@router.get("/watchlists", response_model=list[WatchlistResponse])
def list_watchlists(db: Session = Depends(get_db)):
    return list(db.scalars(select(Watchlist).order_by(Watchlist.name)))


@router.post("/watchlists", response_model=WatchlistResponse, status_code=201)
def create_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db)):
    item = Watchlist(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/watchlists/{watchlist_id}", response_model=WatchlistResponse)
def get_watchlist(watchlist_id: int, db: Session = Depends(get_db)):
    item = db.scalar(select(Watchlist).where(Watchlist.id == watchlist_id))
    if not item:
        raise HTTPException(404, "Watchlist not found")
    return item


@router.patch("/watchlists/{watchlist_id}", response_model=WatchlistResponse)
def update_watchlist(watchlist_id: int, payload: WatchlistUpdate, db: Session = Depends(get_db)):
    item = db.scalar(select(Watchlist).where(Watchlist.id == watchlist_id))
    if not item:
        raise HTTPException(404, "Watchlist not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/watchlists/{watchlist_id}", status_code=204)
def delete_watchlist(watchlist_id: int, db: Session = Depends(get_db)):
    item = db.scalar(select(Watchlist).where(Watchlist.id == watchlist_id))
    if not item:
        raise HTTPException(404, "Watchlist not found")
    db.delete(item)
    db.commit()


@router.get("/watchlists/{watchlist_id}/items", response_model=list[WatchlistItemResponse])
def list_watchlist_items(watchlist_id: int, db: Session = Depends(get_db)):
    if not db.scalar(select(Watchlist).where(Watchlist.id == watchlist_id)):
        raise HTTPException(404, "Watchlist not found")
    rows = db.execute(
        select(WatchlistItem, Instrument)
        .join(Instrument, Instrument.id == WatchlistItem.instrument_id)
        .where(WatchlistItem.watchlist_id == watchlist_id)
        .order_by(WatchlistItem.priority.desc(), Instrument.symbol)
    )
    return [
        WatchlistItemResponse(
            id=item.id,
            watchlist_id=item.watchlist_id,
            instrument_id=item.instrument_id,
            symbol=instrument.symbol,
            company_name=instrument.company_name,
            market=instrument.market,
            priority=item.priority,
        )
        for item, instrument in rows
    ]


@router.post(
    "/watchlists/{watchlist_id}/items", response_model=WatchlistItemResponse, status_code=201
)
def add_watchlist_item(
    watchlist_id: int,
    payload: WatchlistItemCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if not db.scalar(select(Watchlist).where(Watchlist.id == watchlist_id)):
        raise HTTPException(404, "Watchlist not found")
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == payload.symbol.upper()))
    if not instrument:
        raise HTTPException(404, "Company not found")
    if db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.instrument_id == instrument.id
        )
    ):
        raise HTTPException(409, "Company is already in this watchlist")
    item = WatchlistItem(
        watchlist_id=watchlist_id, instrument_id=instrument.id, priority=payload.priority
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    if get_settings().initial_price_backfill_days > 0:
        background_tasks.add_task(run_price_history_backfill_sync, instrument.symbol)
    return WatchlistItemResponse(
        id=item.id,
        watchlist_id=watchlist_id,
        instrument_id=instrument.id,
        symbol=instrument.symbol,
        company_name=instrument.company_name,
        market=instrument.market,
        priority=item.priority,
    )


@router.delete("/watchlists/{watchlist_id}/items/{instrument_id}", status_code=204)
def remove_watchlist_item(watchlist_id: int, instrument_id: int, db: Session = Depends(get_db)):
    item = db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.instrument_id == instrument_id
        )
    )
    if not item:
        raise HTTPException(404, "Watchlist item not found")
    db.delete(item)
    db.commit()


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return list(db.scalars(select(JobRun).order_by(desc(JobRun.started_at)).limit(limit)))


@router.get("/alerts", response_model=list[AlertResponse])
def list_alerts(db: Session = Depends(get_db)):
    return list(db.scalars(select(Alert).order_by(Alert.name)))


@router.post("/alerts", response_model=AlertResponse, status_code=201)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)):
    values = payload.model_dump()
    values["market"] = payload.market.upper() if payload.market else None
    alert = Alert(**values)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.patch("/alerts/{alert_id}", response_model=AlertResponse)
def update_alert(alert_id: int, payload: AlertUpdate, db: Session = Depends(get_db)):
    alert = db.scalar(select(Alert).where(Alert.id == alert_id))
    if not alert:
        raise HTTPException(404, "Alert not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("market"):
        values["market"] = values["market"].upper()
    for key, value in values.items():
        setattr(alert, key, value)
    db.commit()
    db.refresh(alert)
    return alert


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.scalar(select(Alert).where(Alert.id == alert_id))
    if not alert:
        raise HTTPException(404, "Alert not found")
    db.delete(alert)
    db.commit()


@router.get("/alerts/deliveries", response_model=list[AlertDeliveryResponse])
def list_alert_deliveries(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return list(
        db.scalars(select(AlertDelivery).order_by(desc(AlertDelivery.delivered_at)).limit(limit))
    )


@router.post("/alerts/evaluate", response_model=list[AlertDeliveryResponse])
async def evaluate_alert_deliveries(db: Session = Depends(get_db)):
    deliveries = evaluate_alerts(db)
    db.commit()
    return deliveries


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.scalar(select(JobRun).where(JobRun.id == job_id))
    if not job:
        raise HTTPException(404, "Job not found")
    return job
