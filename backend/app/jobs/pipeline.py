import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select

from app.changes.engine import (
    detect_estimate_changes,
    detect_flow_changes,
    detect_fundamental_changes,
    detect_price_changes,
)
from app.config import get_settings
from app.db.models import (
    Change,
    DataSource,
    EstimateSnapshot,
    Event,
    FlowDaily,
    FundamentalSnapshot,
    Instrument,
    JobRun,
    PriceDaily,
    RawIngestion,
)
from app.db.session import SessionLocal
from app.providers.base import Provider
from app.providers.fixture import FixtureProvider
from app.providers.live import LiveProvider


def _instrument(db, symbol: str) -> Instrument | None:
    return db.scalar(select(Instrument).where(Instrument.symbol == symbol))


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
        metadata_={"normalized": True},
    )
    db.add(row)
    db.flush()
    return row


async def run_fixture_pipeline() -> dict[str, int]:
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
        if not twse or not alpha:
            raise RuntimeError("Run `python -m app.seed` before the pipeline")
        instruments = list(
            db.scalars(select(Instrument).where(Instrument.is_active.is_(True)))
        )
        symbols = [row.symbol for row in instruments]
        prices = await provider.prices(symbols)
        estimates = await provider.estimates(symbols)
        flows = await provider.flows(symbols)
        events = await provider.events(symbols)
        fundamentals = await provider.fundamentals(symbols)
        inserted = 0

        for observation in prices:
            instrument = _instrument(db, observation.symbol)
            if not instrument:
                continue
            source = twse if instrument.market == "TW" else alpha
            raw = _raw(db, source.id, provider, "prices", instrument.id, observation)
            exists = db.scalar(
                select(PriceDaily).where(
                    PriceDaily.instrument_id == instrument.id,
                    PriceDaily.source_id == source.id,
                    PriceDaily.trading_date == observation.trading_date,
                )
            )
            if not exists:
                db.add(PriceDaily(
                    instrument_id=instrument.id, source_id=source.id,
                    raw_ingestion_id=raw.id, trading_date=observation.trading_date,
                    close=observation.close, volume=observation.volume,
                ))
                inserted += 1

        for observation in flows:
            instrument = _instrument(db, observation.symbol)
            if not instrument:
                continue
            raw = _raw(db, twse.id, provider, "flows", instrument.id, observation)
            exists = db.scalar(select(FlowDaily).where(
                FlowDaily.instrument_id == instrument.id,
                FlowDaily.source_id == twse.id,
                FlowDaily.trading_date == observation.trading_date,
                FlowDaily.flow_type == observation.flow_type,
            ))
            if not exists:
                db.add(FlowDaily(
                    instrument_id=instrument.id, source_id=twse.id,
                    raw_ingestion_id=raw.id, trading_date=observation.trading_date,
                    flow_type=observation.flow_type, net_volume=observation.net_volume,
                    unit="shares",
                ))
                inserted += 1

        for observation in fundamentals:
            instrument = _instrument(db, observation.symbol)
            if not instrument:
                continue
            raw = _raw(db, twse.id, provider, "fundamentals", instrument.id, observation)
            exists = db.scalar(select(FundamentalSnapshot).where(
                FundamentalSnapshot.instrument_id == instrument.id,
                FundamentalSnapshot.source_id == twse.id,
                FundamentalSnapshot.metric == observation.metric,
                FundamentalSnapshot.period_label == observation.period,
                FundamentalSnapshot.observed_at == observation.observed_at,
            ))
            if not exists:
                db.add(FundamentalSnapshot(
                    instrument_id=instrument.id, source_id=twse.id,
                    raw_ingestion_id=raw.id, metric=observation.metric,
                    period_label=observation.period, value=observation.value,
                    unit=observation.unit, observed_at=observation.observed_at,
                ))
                inserted += 1

        for observation in estimates:
            instrument = _instrument(db, observation.symbol)
            if not instrument:
                continue
            raw = _raw(db, alpha.id, provider, "estimates", instrument.id, observation)
            exists = db.scalar(select(EstimateSnapshot).where(
                EstimateSnapshot.instrument_id == instrument.id,
                EstimateSnapshot.source_id == alpha.id,
                EstimateSnapshot.metric == observation.metric,
                EstimateSnapshot.fiscal_period_label == observation.fiscal_period,
                EstimateSnapshot.observed_at == observation.observed_at,
            ))
            if not exists:
                db.add(EstimateSnapshot(
                    instrument_id=instrument.id, source_id=alpha.id,
                    raw_ingestion_id=raw.id, metric=observation.metric,
                    fiscal_period_label=observation.fiscal_period, value=observation.value,
                    unit="USD", observed_at=observation.observed_at,
                ))
                inserted += 1

        for observation in events:
            instrument = _instrument(db, observation.symbol) if observation.symbol else None
            exists = db.scalar(select(Event).where(
                Event.instrument_id == instrument.id if instrument else Event.instrument_id.is_(None),
                Event.event_type == observation.event_type,
                Event.title == observation.title,
                Event.event_date == observation.event_date,
            ))
            if not exists:
                db.add(Event(
                    instrument_id=instrument.id if instrument else None, source_id=twse.id,
                    event_type=observation.event_type, title=observation.title,
                    event_date=observation.event_date, source_url=observation.source_url,
                    status="scheduled",
                ))
                inserted += 1

        db.flush()
        candidates = []
        for instrument in instruments:
            candidates.extend(detect_price_changes(db, instrument))
            candidates.extend(detect_estimate_changes(db, instrument))
            candidates.extend(detect_fundamental_changes(db, instrument))
            candidates.extend(detect_flow_changes(db, instrument))
        changes_inserted = 0
        for change in candidates:
            duplicate = db.scalar(select(Change).where(
                Change.instrument_id == change.instrument_id,
                Change.category == change.category,
                Change.metric == change.metric,
                Change.period == change.period,
                Change.current_snapshot_type == change.current_snapshot_type,
                Change.current_snapshot_id == change.current_snapshot_id,
                Change.previous_snapshot_id == change.previous_snapshot_id,
            ))
            if not duplicate:
                db.add(change)
                changes_inserted += 1

        job.finished_at = datetime.now(UTC)
        job.status = "success"
        job.items_requested = len(symbols)
        job.items_fetched = len(prices) + len(estimates) + len(flows) + len(events) + len(fundamentals)
        job.items_inserted = inserted
        job.items_changed = changes_inserted
        db.commit()
        return {
            "prices": len(prices),
            "estimates": len(estimates),
            "flows": len(flows),
            "events": len(events),
            "fundamentals": len(fundamentals),
            "snapshots_inserted": inserted,
            "changes_detected": changes_inserted,
        }


if __name__ == "__main__":
    import asyncio

    print(asyncio.run(run_fixture_pipeline()))
