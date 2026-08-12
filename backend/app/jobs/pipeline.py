import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import delete, func, select

from app.alerts.service import evaluate_alerts
from app.changes.engine import (
    detect_estimate_changes,
    detect_event_changes,
    detect_flow_changes,
    detect_fundamental_changes,
    detect_news_changes,
    detect_ownership_changes,
    detect_price_changes,
)
from app.config import get_settings
from app.db.models import (
    AIInterpretation,
    AlertDelivery,
    Change,
    DataSource,
    EstimateSnapshot,
    Event,
    FlowDaily,
    FundamentalSnapshot,
    Instrument,
    InstrumentAlias,
    JobRun,
    MacroSnapshot,
    NewsInstrument,
    NewsItem,
    OwnershipSnapshot,
    PriceDaily,
    RawIngestion,
    WatchlistItem,
)
from app.db.session import SessionLocal
from app.providers.base import Provider
from app.providers.fixture import FixtureProvider
from app.providers.live import LiveProvider, _latest_closed_us_trading_date
from app.reports.daily import generate_daily_reports
from app.scoring.scorer import WEIGHTS, freshness_score, severity


async def _fetch_domain[Observation](
    name: str,
    fetch: Callable[[], Awaitable[list[Observation]]],
    errors: list[str],
) -> list[Observation]:
    """Keep one provider failure from suppressing unrelated market domains."""
    try:
        return await fetch()
    except Exception as exc:  # noqa: BLE001  # provider boundaries must be isolated per domain
        errors.append(f"{name}: {type(exc).__name__}: {exc}")
        return []


def _refresh_news_scores(db, *, now: datetime | None = None) -> None:
    """Keep persisted news signals in step with their publication-time decay."""
    now = now or datetime.now(UTC)
    rows = db.execute(
        select(Change, NewsItem)
        .join(NewsItem, NewsItem.id == Change.current_snapshot_id)
        .where(Change.category == "news", Change.current_snapshot_type == "news_items")
    )
    for change, news in rows:
        change.freshness_score = freshness_score("news", news.published_at, now=now)
        total = sum(
            value * WEIGHTS[key]
            for key, value in {
                "magnitude": change.magnitude_score,
                "rarity": change.rarity_score,
                "relevance": change.relevance_score,
                "freshness": change.freshness_score,
                "source_quality": change.source_quality_score,
            }.items()
        )
        change.total_score = round(max(0, min(100, total)), 2)
        change.severity = severity(change.total_score)


def _instrument(db, symbol: str) -> Instrument | None:
    return db.scalar(select(Instrument).where(Instrument.symbol == symbol))


def _persist_new_changes(db, candidates: list[Change]) -> int:
    """Store detector output once, keyed by the snapshots it compares."""
    inserted = 0
    for change in candidates:
        duplicate = db.scalar(
            select(Change).where(
                Change.instrument_id == change.instrument_id,
                Change.category == change.category,
                Change.metric == change.metric,
                Change.period == change.period,
                Change.current_snapshot_type == change.current_snapshot_type,
                Change.current_snapshot_id == change.current_snapshot_id,
                Change.previous_snapshot_id == change.previous_snapshot_id,
            )
        )
        if not duplicate:
            db.add(change)
            inserted += 1
    return inserted


def _normalized_headline(headline: str) -> str:
    """Provider-neutral key for syndicated headlines."""
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", headline.lower())


def _is_duplicate_news(db, observation, instrument: Instrument | None) -> bool:
    """Reject URL duplicates and near-identical syndicated headlines."""
    by_url = db.scalar(select(NewsItem).where(NewsItem.source_url == observation.source_url))
    if by_url:
        return True
    lower = observation.published_at - timedelta(hours=12)
    upper = observation.published_at + timedelta(hours=12)
    query = select(NewsItem).where(NewsItem.published_at.between(lower, upper))
    if instrument:
        query = query.join(NewsInstrument).where(NewsInstrument.instrument_id == instrument.id)
    normalized = _normalized_headline(observation.headline)
    for existing in db.scalars(query):
        candidate = _normalized_headline(existing.headline)
        if normalized == candidate or SequenceMatcher(None, normalized, candidate).ratio() >= 0.9:
            return True
    return False


def _raw(db, source_id: int, provider: Provider, endpoint: str, instrument_id: int, observation):
    payload = observation.model_dump(mode="json")
    row = RawIngestion(
        source_id=source_id,
        provider_endpoint=f"{provider.name}/{endpoint}",
        instrument_id=instrument_id,
        source_data_date=getattr(observation, "trading_date", None),
        fetched_at=datetime.now(UTC),
        http_status=200,
        status="success",
        content_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        payload=payload,
        raw_text=json.dumps(payload, sort_keys=True),
        metadata_={"normalized": True, "payload_format": "normalized_observation"},
    )
    db.add(row)
    db.flush()
    return row


def _remove_untracked_data(db) -> int:
    """Remove snapshots and derived records once an instrument leaves every watchlist."""
    tracked_instrument_ids = select(WatchlistItem.instrument_id).distinct()
    untracked_instrument_ids = select(Instrument.id).where(
        Instrument.id.not_in(tracked_instrument_ids)
    )
    untracked_change_ids = select(Change.id).where(
        Change.instrument_id.in_(untracked_instrument_ids)
    )
    db.execute(delete(AlertDelivery).where(AlertDelivery.change_id.in_(untracked_change_ids)))
    db.execute(
        delete(AIInterpretation).where(AIInterpretation.instrument_id.in_(untracked_instrument_ids))
    )
    db.execute(delete(Change).where(Change.instrument_id.in_(untracked_instrument_ids)))
    db.execute(delete(PriceDaily).where(PriceDaily.instrument_id.in_(untracked_instrument_ids)))
    db.execute(delete(FlowDaily).where(FlowDaily.instrument_id.in_(untracked_instrument_ids)))
    db.execute(
        delete(EstimateSnapshot).where(EstimateSnapshot.instrument_id.in_(untracked_instrument_ids))
    )
    db.execute(
        delete(FundamentalSnapshot).where(
            FundamentalSnapshot.instrument_id.in_(untracked_instrument_ids)
        )
    )
    db.execute(
        delete(OwnershipSnapshot).where(
            OwnershipSnapshot.instrument_id.in_(untracked_instrument_ids)
        )
    )
    db.execute(delete(Event).where(Event.instrument_id.in_(untracked_instrument_ids)))
    db.execute(
        delete(NewsInstrument).where(NewsInstrument.instrument_id.in_(untracked_instrument_ids))
    )
    db.execute(delete(NewsItem).where(NewsItem.id.not_in(select(NewsInstrument.news_item_id))))
    result = db.execute(
        delete(RawIngestion).where(RawIngestion.instrument_id.in_(untracked_instrument_ids))
    )
    return result.rowcount or 0


def _remove_unclosed_us_price_data(db) -> int:
    """Discard any US daily bars that were persisted before their session closed."""
    invalid_snapshot_ids = (
        select(PriceDaily.id)
        .join(Instrument)
        .where(
            Instrument.market == "US",
            PriceDaily.trading_date > _latest_closed_us_trading_date(),
        )
    )
    invalid_change_ids = select(Change.id).where(
        Change.current_snapshot_type == "price_daily",
        Change.current_snapshot_id.in_(invalid_snapshot_ids),
    )
    db.execute(delete(AlertDelivery).where(AlertDelivery.change_id.in_(invalid_change_ids)))
    db.execute(delete(Change).where(Change.id.in_(invalid_change_ids)))
    result = db.execute(delete(PriceDaily).where(PriceDaily.id.in_(invalid_snapshot_ids)))
    return result.rowcount or 0


async def run_price_history_backfill(symbol: str) -> dict[str, int | str]:
    """Backfill one newly watched instrument without waiting for the full pipeline."""
    provider: Provider = LiveProvider() if get_settings().mce_use_live else FixtureProvider()
    with SessionLocal() as db:
        instrument = _instrument(db, symbol)
        if not instrument:
            return {"status": "skipped", "snapshots_inserted": 0}

        job = JobRun(
            job_name="price_history_backfill",
            started_at=datetime.now(UTC),
            status="running",
            items_requested=1,
        )
        db.add(job)
        db.flush()
        errors: list[str] = []
        start_date = (
            datetime.now(UTC) - timedelta(days=get_settings().initial_price_backfill_days)
        ).date()
        prices = await _fetch_domain(
            "price_history", lambda: provider.price_history([instrument.symbol], start_date), errors
        )
        source_code = "twse" if instrument.market == "TW" else "yfinance"
        source = db.scalar(select(DataSource).where(DataSource.code == source_code))
        if not source:
            errors.append(f"price_history: missing data source {source_code}")

        inserted = 0
        if source:
            for observation in prices:
                raw = _raw(db, source.id, provider, "price_history", instrument.id, observation)
                exists = db.scalar(
                    select(PriceDaily).where(
                        PriceDaily.instrument_id == instrument.id,
                        PriceDaily.source_id == source.id,
                        PriceDaily.trading_date == observation.trading_date,
                    )
                )
                if not exists:
                    db.add(
                        PriceDaily(
                            instrument_id=instrument.id,
                            source_id=source.id,
                            raw_ingestion_id=raw.id,
                            trading_date=observation.trading_date,
                            close=observation.close,
                            volume=observation.volume,
                        )
                    )
                    inserted += 1

        db.flush()
        changes_inserted = _persist_new_changes(db, detect_price_changes(db, instrument))
        job.finished_at = datetime.now(UTC)
        job.status = "partial" if errors else "success"
        job.items_fetched = len(prices)
        job.items_inserted = inserted
        job.items_changed = changes_inserted
        job.items_failed = len(errors)
        job.error_summary = "; ".join(errors) if errors else None
        db.commit()
        return {
            "status": job.status,
            "prices": len(prices),
            "snapshots_inserted": inserted,
            "changes_detected": changes_inserted,
            "failed_domains": len(errors),
        }


def run_price_history_backfill_sync(symbol: str) -> None:
    """Sync adapter for FastAPI background tasks."""
    import asyncio

    asyncio.run(run_price_history_backfill(symbol))


async def run_fixture_pipeline() -> dict[str, int | str]:
    provider: Provider = LiveProvider() if get_settings().mce_use_live else FixtureProvider()
    with SessionLocal() as db:
        job = JobRun(
            job_name="market_pipeline",
            started_at=datetime.now(UTC),
            status="running",
        )
        db.add(job)
        db.flush()
        twse = db.scalar(select(DataSource).where(DataSource.code == "twse"))
        alpha = db.scalar(select(DataSource).where(DataSource.code == "alphavantage"))
        news_source = db.scalar(select(DataSource).where(DataSource.code == "google_news")) or alpha
        mops = db.scalar(select(DataSource).where(DataSource.code == "mops")) or twse
        tdcc = db.scalar(select(DataSource).where(DataSource.code == "tdcc")) or twse
        sec = db.scalar(select(DataSource).where(DataSource.code == "sec")) or alpha
        sec_filings = db.scalar(select(DataSource).where(DataSource.code == "sec_filings")) or sec
        fred = db.scalar(select(DataSource).where(DataSource.code == "fred"))
        if not twse or not alpha:
            job.status = "failed"
            job.finished_at = datetime.now(UTC)
            job.error_summary = "Required data sources are missing; run `python -m app.seed`."
            job.items_failed = 1
            db.commit()
            raise RuntimeError("Run `python -m app.seed` before the pipeline")
        removed_records = _remove_untracked_data(db)
        removed_unclosed_prices = (
            _remove_unclosed_us_price_data(db) if get_settings().mce_use_live else 0
        )
        instruments = list(
            db.scalars(
                select(Instrument)
                .join(WatchlistItem, WatchlistItem.instrument_id == Instrument.id)
                .where(Instrument.is_active.is_(True))
                .distinct()
            )
        )
        symbols = [row.symbol for row in instruments]
        search_terms = {
            instrument.symbol: [
                instrument.company_name,
                *db.scalars(
                    select(InstrumentAlias.alias).where(
                        InstrumentAlias.instrument_id == instrument.id
                    )
                ),
            ]
            for instrument in instruments
        }
        errors: list[str] = []
        backfill_days = get_settings().initial_price_backfill_days
        latest_price_dates = dict(
            db.execute(
                select(PriceDaily.instrument_id, func.max(PriceDaily.trading_date))
                .where(PriceDaily.instrument_id.in_([instrument.id for instrument in instruments]))
                .group_by(PriceDaily.instrument_id)
            ).all()
        )
        market_trading_dates: dict[str, set] = {}
        for market, trading_date in db.execute(
            select(Instrument.market, PriceDaily.trading_date)
            .join(PriceDaily, PriceDaily.instrument_id == Instrument.id)
            .distinct()
        ):
            market_trading_dates.setdefault(market, set()).add(trading_date)
        stale_before_by_market = {
            market: sorted(trading_dates, reverse=True)[3]
            for market, trading_dates in market_trading_dates.items()
            if len(trading_dates) > 3
        }
        watchlist_instrument_ids = set(db.scalars(select(WatchlistItem.instrument_id).distinct()))
        symbols_needing_price_history = [
            instrument.symbol
            for instrument in instruments
            if (
                instrument.id in watchlist_instrument_ids
                and (
                    instrument.id not in latest_price_dates
                    or (
                        instrument.market in stale_before_by_market
                        and latest_price_dates[instrument.id]
                        < stale_before_by_market[instrument.market]
                    )
                )
            )
        ]
        symbols_needing_price_history_set = set(symbols_needing_price_history)
        symbols_with_prices = [
            instrument.symbol
            for instrument in instruments
            if instrument.symbol not in symbols_needing_price_history_set
        ]
        prices = []
        if symbols_needing_price_history and backfill_days > 0:
            start_date = (datetime.now(UTC) - timedelta(days=backfill_days)).date()
            prices.extend(
                await _fetch_domain(
                    "price_history",
                    lambda: provider.price_history(symbols_needing_price_history, start_date),
                    errors,
                )
            )
        else:
            symbols_with_prices = symbols
        if symbols_with_prices:
            prices.extend(
                await _fetch_domain("prices", lambda: provider.prices(symbols_with_prices), errors)
            )
        estimates = await _fetch_domain("estimates", lambda: provider.estimates(symbols), errors)
        flows = await _fetch_domain("flows", lambda: provider.flows(symbols), errors)
        events = await _fetch_domain("events", lambda: provider.events(symbols), errors)
        ownership = await _fetch_domain("ownership", lambda: provider.ownership(symbols), errors)
        news = await _fetch_domain(
            "news", lambda: provider.news(symbols, search_terms=search_terms), errors
        )
        fundamentals = await _fetch_domain(
            "fundamentals", lambda: provider.fundamentals(symbols), errors
        )
        macro = await _fetch_domain("macro", provider.macro, errors)
        inserted = 0

        for observation in prices:
            instrument = _instrument(db, observation.symbol)
            if not instrument:
                continue
            source_code = observation.source_code or (
                "twse" if instrument.market == "TW" else "yfinance"
            )
            source = db.scalar(select(DataSource).where(DataSource.code == source_code))
            if source is None:
                errors.append(f"prices: missing data source {source_code}")
                continue
            raw = _raw(db, source.id, provider, "prices", instrument.id, observation)
            exists = db.scalar(
                select(PriceDaily).where(
                    PriceDaily.instrument_id == instrument.id,
                    PriceDaily.source_id == source.id,
                    PriceDaily.trading_date == observation.trading_date,
                )
            )
            if not exists:
                db.add(
                    PriceDaily(
                        instrument_id=instrument.id,
                        source_id=source.id,
                        raw_ingestion_id=raw.id,
                        trading_date=observation.trading_date,
                        close=observation.close,
                        volume=observation.volume,
                    )
                )
                inserted += 1

        for observation in flows:
            instrument = _instrument(db, observation.symbol)
            if not instrument:
                continue
            raw = _raw(db, twse.id, provider, "flows", instrument.id, observation)
            exists = db.scalar(
                select(FlowDaily).where(
                    FlowDaily.instrument_id == instrument.id,
                    FlowDaily.source_id == twse.id,
                    FlowDaily.trading_date == observation.trading_date,
                    FlowDaily.flow_type == observation.flow_type,
                )
            )
            if not exists:
                db.add(
                    FlowDaily(
                        instrument_id=instrument.id,
                        source_id=twse.id,
                        raw_ingestion_id=raw.id,
                        trading_date=observation.trading_date,
                        flow_type=observation.flow_type,
                        net_volume=observation.net_volume,
                        unit="shares",
                    )
                )
                inserted += 1

        for observation in fundamentals:
            instrument = _instrument(db, observation.symbol)
            if not instrument:
                continue
            source = sec if observation.unit == "USD" and instrument.market == "US" else mops
            raw = _raw(db, source.id, provider, "fundamentals", instrument.id, observation)
            exists = db.scalar(
                select(FundamentalSnapshot).where(
                    FundamentalSnapshot.instrument_id == instrument.id,
                    FundamentalSnapshot.source_id == source.id,
                    FundamentalSnapshot.metric == observation.metric,
                    FundamentalSnapshot.period_label == observation.period,
                    FundamentalSnapshot.observed_at == observation.observed_at,
                )
            )
            if not exists:
                db.add(
                    FundamentalSnapshot(
                        instrument_id=instrument.id,
                        source_id=source.id,
                        raw_ingestion_id=raw.id,
                        metric=observation.metric,
                        period_label=observation.period,
                        value=observation.value,
                        unit=observation.unit,
                        observed_at=observation.observed_at,
                    )
                )
                inserted += 1

        if fred is None and macro:
            errors.append("macro: missing data source fred")
        elif fred:
            for observation in macro:
                exists = db.scalar(
                    select(MacroSnapshot).where(
                        MacroSnapshot.source_id == fred.id,
                        MacroSnapshot.series_id == observation.series_id,
                        MacroSnapshot.observation_date == observation.observation_date,
                    )
                )
                if exists:
                    continue
                db.add(
                    MacroSnapshot(
                        source_id=fred.id,
                        series_id=observation.series_id,
                        observation_date=observation.observation_date,
                        value=observation.value,
                        unit=observation.unit,
                        observed_at=observation.observed_at,
                    )
                )
                inserted += 1

        for observation in estimates:
            instrument = _instrument(db, observation.symbol)
            if not instrument:
                continue
            raw = _raw(db, alpha.id, provider, "estimates", instrument.id, observation)
            exists = db.scalar(
                select(EstimateSnapshot).where(
                    EstimateSnapshot.instrument_id == instrument.id,
                    EstimateSnapshot.source_id == alpha.id,
                    EstimateSnapshot.metric == observation.metric,
                    EstimateSnapshot.fiscal_period_label == observation.fiscal_period,
                    EstimateSnapshot.observed_at == observation.observed_at,
                )
            )
            if not exists:
                db.add(
                    EstimateSnapshot(
                        instrument_id=instrument.id,
                        source_id=alpha.id,
                        raw_ingestion_id=raw.id,
                        metric=observation.metric,
                        fiscal_period_label=observation.fiscal_period,
                        value=observation.value,
                        unit=observation.unit,
                        observed_at=observation.observed_at,
                    )
                )
                inserted += 1

        for observation in events:
            instrument = _instrument(db, observation.symbol) if observation.symbol else None
            source = (
                sec_filings
                if observation.source_code == "sec_filings"
                else alpha
                if observation.source_code == "alphavantage"
                or (instrument and instrument.market == "US")
                else twse
            )
            exists = db.scalar(
                select(Event).where(
                    Event.instrument_id == instrument.id
                    if instrument
                    else Event.instrument_id.is_(None),
                    Event.event_type == observation.event_type,
                    Event.title == observation.title,
                    Event.event_date == observation.event_date,
                )
            )
            if not exists:
                raw = _raw(
                    db,
                    source.id,
                    provider,
                    "events",
                    instrument.id if instrument else None,
                    observation,
                )
                db.add(
                    Event(
                        instrument_id=instrument.id if instrument else None,
                        source_id=source.id,
                        raw_ingestion_id=raw.id,
                        event_type=observation.event_type,
                        title=observation.title,
                        event_date=observation.event_date,
                        source_url=observation.source_url,
                        status="scheduled",
                    )
                )
                inserted += 1

        for observation in ownership:
            instrument = _instrument(db, observation.symbol)
            if not instrument:
                continue
            raw = _raw(db, tdcc.id, provider, "ownership", instrument.id, observation)
            exists = db.scalar(
                select(OwnershipSnapshot).where(
                    OwnershipSnapshot.instrument_id == instrument.id,
                    OwnershipSnapshot.source_id == tdcc.id,
                    OwnershipSnapshot.snapshot_date == observation.snapshot_date,
                    OwnershipSnapshot.holder_bucket == observation.holder_bucket,
                )
            )
            if not exists:
                db.add(
                    OwnershipSnapshot(
                        instrument_id=instrument.id,
                        source_id=tdcc.id,
                        raw_ingestion_id=raw.id,
                        snapshot_date=observation.snapshot_date,
                        holder_bucket=observation.holder_bucket,
                        holder_count=observation.holder_count,
                        share_count=observation.share_count,
                        ownership_pct=observation.ownership_pct,
                    )
                )
                inserted += 1

        oldest_news_allowed = datetime.now(UTC) - timedelta(days=get_settings().news_max_age_days)
        for observation in news:
            if observation.published_at < oldest_news_allowed:
                continue
            instrument = _instrument(db, observation.symbol) if observation.symbol else None
            duplicate = (
                db.scalar(
                    select(NewsItem).where(
                        NewsItem.source_id == news_source.id,
                        NewsItem.external_id == observation.external_id,
                    )
                )
                if observation.external_id
                else None
            )
            if duplicate or _is_duplicate_news(db, observation, instrument):
                continue
            raw = _raw(
                db,
                news_source.id,
                provider,
                "news",
                instrument.id if instrument else None,
                observation,
            )
            item = NewsItem(
                source_id=news_source.id,
                raw_ingestion_id=raw.id,
                external_id=observation.external_id,
                headline=observation.headline,
                published_at=observation.published_at,
                source_name=observation.source_name,
                source_url=observation.source_url,
                category=observation.category,
                importance_score=observation.importance_score,
                is_material=observation.is_material,
                summary=observation.summary,
                metadata_={},
            )
            db.add(item)
            db.flush()
            if instrument:
                db.add(
                    NewsInstrument(
                        news_item_id=item.id, instrument_id=instrument.id, relevance_score=100
                    )
                )
            inserted += 1

        db.flush()
        candidates = []
        for instrument in instruments:
            candidates.extend(detect_price_changes(db, instrument))
            candidates.extend(detect_estimate_changes(db, instrument))
            candidates.extend(detect_fundamental_changes(db, instrument))
            candidates.extend(detect_flow_changes(db, instrument))
            candidates.extend(detect_ownership_changes(db, instrument))
            candidates.extend(detect_event_changes(db, instrument))
            candidates.extend(detect_news_changes(db, instrument))
        changes_inserted = _persist_new_changes(db, candidates)

        db.flush()
        _refresh_news_scores(db)
        generate_daily_reports(db)
        evaluate_alerts(db)
        job.finished_at = datetime.now(UTC)
        job.status = "partial" if errors else "success"
        job.items_requested = len(symbols)
        job.items_fetched = (
            len(prices)
            + len(estimates)
            + len(flows)
            + len(events)
            + len(ownership)
            + len(news)
            + len(fundamentals)
        )
        job.items_inserted = inserted
        job.items_changed = changes_inserted
        job.items_failed = len(errors)
        job.error_summary = "; ".join(errors) if errors else None
        db.commit()
        return {
            "prices": len(prices),
            "estimates": len(estimates),
            "flows": len(flows),
            "events": len(events),
            "ownership": len(ownership),
            "news": len(news),
            "fundamentals": len(fundamentals),
            "macro": len(macro),
            "snapshots_inserted": inserted,
            "changes_detected": changes_inserted,
            "failed_domains": len(errors),
            "untracked_records_removed": removed_records,
            "unclosed_us_prices_removed": removed_unclosed_prices,
            "status": job.status,
        }


if __name__ == "__main__":
    import asyncio

    print(asyncio.run(run_fixture_pipeline()))
