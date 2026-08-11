from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    ChangeResponse,
    EventResponse,
    HistoryPoint,
    InstrumentResponse,
    JobResponse,
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistResponse,
)
from app.db.models import (
    Change,
    EstimateSnapshot,
    Event,
    FlowDaily,
    FundamentalSnapshot,
    Instrument,
    JobRun,
    PriceDaily,
    Watchlist,
    WatchlistItem,
)
from app.db.session import get_db

router = APIRouter()


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
    db: Session = Depends(get_db),
):
    query = (
        select(Change, Instrument)
        .join(Instrument, Instrument.id == Change.instrument_id)
        .where(
            Change.total_score >= min_score,
            Change.detected_at >= datetime.now(UTC) - timedelta(hours=hours),
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
    return [
        ChangeResponse(
            id=change.id,
            symbol=instrument.symbol,
            company_name=instrument.company_name,
            market=instrument.market,
            category=change.category,
            metric=change.metric,
            period=change.period,
            previous_value=change.previous_value,
            current_value=change.current_value,
            absolute_change=change.absolute_change,
            percentage_change=change.percentage_change,
            direction=change.direction,
            severity=change.severity,
            total_score=change.total_score,
            detected_at=change.detected_at,
        )
        for change, instrument in db.execute(query)
    ]


@router.get("/companies", response_model=list[InstrumentResponse])
def list_companies(db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(Instrument).where(Instrument.is_active.is_(True)).order_by(Instrument.symbol)
        )
    )


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
    changes = db.scalars(
        select(Change)
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
            previous_value=change.previous_value,
            current_value=change.current_value,
            absolute_change=change.absolute_change,
            percentage_change=change.percentage_change,
            direction=change.direction,
            severity=change.severity,
            total_score=change.total_score,
            detected_at=change.detected_at,
        )
        for change in changes
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
    watchlist_id: int, payload: WatchlistItemCreate, db: Session = Depends(get_db)
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


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.scalar(select(JobRun).where(JobRun.id == job_id))
    if not job:
        raise HTTPException(404, "Job not found")
    return job
