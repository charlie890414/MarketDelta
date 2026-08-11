import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select

from app.changes.engine import detect_estimate_changes, detect_price_changes
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
from app.providers.fixture import FixtureProvider
from app.providers.live import LiveProvider


async def run_fixture_pipeline() -> dict[str, int]:
    provider = LiveProvider() if get_settings().mce_use_live else FixtureProvider()
    with SessionLocal() as db:
        job = JobRun(
            job_name="fixture_market_pipeline",
            started_at=datetime.now(UTC),
            status="running",
        )
        db.add(job)
        db.flush()
        source = db.scalar(select(DataSource).where(DataSource.code == "twse"))
        estimate_source = db.scalar(select(DataSource).where(DataSource.code == "alphavantage"))
        if not source or not estimate_source:
            raise RuntimeError("Run `python -m app.seed` before the pipeline")
        symbols = [
            row.symbol
            for row in db.scalars(select(Instrument).where(Instrument.is_active.is_(True)))
        ]
        prices = await provider.prices(symbols)
        estimates = await provider.estimates(symbols)
        flows = await provider.flows(symbols) if hasattr(provider, "flows") else []
        events = await provider.events(symbols) if hasattr(provider, "events") else []
        fundamentals = (
            await provider.fundamentals(symbols) if hasattr(provider, "fundamentals") else []
        )
        inserted = 0
        for observation in prices:
            instrument = db.scalar(
                select(Instrument).where(Instrument.symbol == observation.symbol)
            )
            if not instrument:
                continue
            payload = observation.model_dump(mode="json")
            price_source = (
                source
                if provider.name == "fixture" or instrument.market == "TW"
                else estimate_source
            )
            raw = RawIngestion(
                source_id=price_source.id,
                provider_endpoint=f"{provider.name}/prices",
                instrument_id=instrument.id,
                source_data_date=observation.trading_date,
                fetched_at=datetime.now(UTC),
                http_status=200,
                status="success",
                content_hash=hashlib.sha256(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest(),
                payload=payload,
                metadata_={},
            )
            db.add(raw)
            db.flush()
            exists = db.scalar(
                select(PriceDaily).where(
                    PriceDaily.instrument_id == instrument.id,
                    PriceDaily.source_id == price_source.id,
                    PriceDaily.trading_date == observation.trading_date,
                )
            )
            if not exists:
                db.add(
                    PriceDaily(
                        instrument_id=instrument.id,
                        source_id=price_source.id,
                        raw_ingestion_id=raw.id,
                        trading_date=observation.trading_date,
                        close=observation.close,
                        volume=observation.volume,
                    )
                )
                inserted += 1
        for observation in flows:
            instrument = db.scalar(
                select(Instrument).where(Instrument.symbol == observation.symbol)
            )
            if not instrument:
                continue
            exists = db.scalar(
                select(FlowDaily).where(
                    FlowDaily.instrument_id == instrument.id,
                    FlowDaily.source_id == source.id,
                    FlowDaily.trading_date == observation.trading_date,
                    FlowDaily.flow_type == observation.flow_type,
                )
            )
            if not exists:
                db.add(
                    FlowDaily(
                        instrument_id=instrument.id,
                        source_id=source.id,
                        trading_date=observation.trading_date,
                        flow_type=observation.flow_type,
                        net_volume=observation.net_volume,
                        unit="shares",
                    )
                )
                inserted += 1
        for observation in events:
            instrument = (
                db.scalar(select(Instrument).where(Instrument.symbol == observation.symbol))
                if observation.symbol
                else None
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
                db.add(
                    Event(
                        instrument_id=instrument.id if instrument else None,
                        source_id=source.id,
                        event_type=observation.event_type,
                        title=observation.title,
                        event_date=observation.event_date,
                        source_url=observation.source_url,
                        status="scheduled",
                    )
                )
                inserted += 1
        for observation in fundamentals:
            instrument = db.scalar(
                select(Instrument).where(Instrument.symbol == observation.symbol)
            )
            if not instrument:
                continue
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
                        metric=observation.metric,
                        period_label=observation.period,
                        value=observation.value,
                        unit=observation.unit,
                        observed_at=observation.observed_at,
                    )
                )
                inserted += 1
        for observation in estimates:
            instrument = db.scalar(
                select(Instrument).where(Instrument.symbol == observation.symbol)
            )
            if not instrument:
                continue
            exists = db.scalar(
                select(EstimateSnapshot).where(
                    EstimateSnapshot.instrument_id == instrument.id,
                    EstimateSnapshot.source_id == estimate_source.id,
                    EstimateSnapshot.metric == observation.metric,
                    EstimateSnapshot.fiscal_period_label == observation.fiscal_period,
                    EstimateSnapshot.observed_at == observation.observed_at,
                )
            )
            if not exists:
                db.add(
                    EstimateSnapshot(
                        instrument_id=instrument.id,
                        source_id=estimate_source.id,
                        metric=observation.metric,
                        fiscal_period_label=observation.fiscal_period,
                        value=observation.value,
                        unit="USD",
                        observed_at=observation.observed_at,
                    )
                )
                inserted += 1
        db.flush()
        changes = []
        for instrument in db.scalars(select(Instrument).where(Instrument.is_active.is_(True))):
            changes.extend(detect_price_changes(db, instrument))
            changes.extend(detect_estimate_changes(db, instrument))
        for change in changes:
            duplicate = db.scalar(
                select(Change).where(
                    Change.instrument_id == change.instrument_id,
                    Change.category == change.category,
                    Change.metric == change.metric,
                    Change.period == change.period,
                    Change.current_snapshot_id == change.current_snapshot_id,
                    Change.previous_snapshot_id == change.previous_snapshot_id,
                )
            )
            if not duplicate:
                db.add(change)
        job.finished_at = datetime.now(UTC)
        job.status = "success"
        job.items_requested = len(symbols)
        job.items_fetched = (
            len(prices) + len(estimates) + len(flows) + len(events) + len(fundamentals)
        )
        job.items_inserted = inserted
        job.items_changed = len(changes)
        db.commit()
        return {
            "prices": len(prices),
            "estimates": len(estimates),
            "flows": len(flows),
            "events": len(events),
            "fundamentals": len(fundamentals),
            "snapshots_inserted": inserted,
            "changes_detected": len(changes),
        }


if __name__ == "__main__":
    import asyncio

    print(asyncio.run(run_fixture_pipeline()))
