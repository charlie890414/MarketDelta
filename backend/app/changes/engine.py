from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.changes.comparator import compare
from app.db.models import (
    Change,
    DataSource,
    EstimateSnapshot,
    FlowDaily,
    FundamentalSnapshot,
    Instrument,
    PriceDaily,
)
from app.domain.observations import ChangeCandidate
from app.scoring.scorer import score_change


def _source_quality(source: DataSource | None) -> float:
    return {"official": 100, "high": 85, "medium": 70, "low": 45}.get(
        source.confidence if source else "low", 50
    )


def _make_change(
    instrument: Instrument,
    current,
    previous,
    *,
    category: str,
    metric: str,
    period: str | None,
    source: DataSource | None,
    snapshot_type: str,
    change_type: str = "changed",
) -> Change | None:
    current_value = (
        current.value
        if hasattr(current, "value")
        else current.net_volume
        if hasattr(current, "net_volume")
        else current.close
    )
    previous_value = (
        previous.value
        if hasattr(previous, "value")
        else previous.net_volume
        if hasattr(previous, "net_volume")
        else previous.close
    )
    if current_value == previous_value:
        return None
    absolute, pct, direction = compare(previous_value, current_value)
    if direction == "up" and previous_value < 0 <= current_value or direction == "down" and previous_value >= 0 > current_value:
        change_type = "reversed"
    candidate = ChangeCandidate(
        symbol=instrument.symbol,
        market=instrument.market,
        category=category,
        metric=metric,
        period=period,
        previous=previous_value,
        current=current_value,
        absolute_change=absolute,
        percentage_change=pct,
        direction=direction,
        change_type=change_type,
        baseline_type="previous",
    )
    observed_at = current.observed_at if hasattr(current, "observed_at") else datetime.combine(
        current.trading_date, datetime.min.time(), tzinfo=UTC
    )
    age_days = max((datetime.now(UTC) - observed_at).total_seconds() / 86400, 0)
    scores = score_change(
        candidate,
        rarity=50,
        freshness=max(0, min(100, 100 - age_days * 10)),
        source_quality=_source_quality(source),
    )
    return Change(
        instrument_id=instrument.id,
        category=category,
        metric=metric,
        period=period,
        baseline_type="previous",
        previous_value=previous_value,
        current_value=current_value,
        absolute_change=absolute,
        percentage_change=pct,
        direction=direction,
        change_type=change_type,
        magnitude_score=scores["magnitude"],
        rarity_score=scores["rarity"],
        relevance_score=scores["relevance"],
        freshness_score=scores["freshness"],
        source_quality_score=scores["source_quality"],
        total_score=scores["total"],
        severity=scores["severity"],
        source_id=current.source_id,
        previous_snapshot_id=previous.id,
        current_snapshot_id=current.id,
        previous_snapshot_type=snapshot_type,
        current_snapshot_type=snapshot_type,
        detected_at=datetime.now(UTC),
        metadata_={},
    )


def _latest_pair(db: Session, model, instrument_id: int, *keys: str):
    query = select(model).where(model.instrument_id == instrument_id)
    for key, value in keys:
        query = query.where(getattr(model, key) == value)
    date_column = model.trading_date if hasattr(model, "trading_date") else model.observed_at
    return list(db.scalars(query.order_by(date_column.desc()).limit(2)))


def detect_price_changes(db: Session, instrument: Instrument) -> list[Change]:
    rows = _latest_pair(db, PriceDaily, instrument.id)
    if len(rows) < 2:
        return []
    source = db.get(DataSource, rows[0].source_id)
    change = _make_change(
        instrument, rows[0], rows[1], category="price", metric="close", period="1d",
        source=source, snapshot_type="price_daily",
    )
    return [change] if change else []


def detect_estimate_changes(db: Session, instrument: Instrument) -> list[Change]:
    rows = list(
        db.scalars(
            select(EstimateSnapshot)
            .where(EstimateSnapshot.instrument_id == instrument.id)
            .order_by(EstimateSnapshot.observed_at.desc())
        )
    )
    grouped: dict[tuple[int, str, str], list[EstimateSnapshot]] = {}
    for row in rows:
        grouped.setdefault((row.source_id, row.metric, row.fiscal_period_label), []).append(row)
    changes = []
    for pair in grouped.values():
        if len(pair) < 2:
            continue
        source = db.get(DataSource, pair[0].source_id)
        change = _make_change(
            instrument, pair[0], pair[1], category="expectation", metric=pair[0].metric,
            period=pair[0].fiscal_period_label, source=source, snapshot_type="estimate_snapshots",
        )
        if change:
            changes.append(change)
    return changes


def detect_fundamental_changes(db: Session, instrument: Instrument) -> list[Change]:
    rows = list(
        db.scalars(
            select(FundamentalSnapshot)
            .where(FundamentalSnapshot.instrument_id == instrument.id)
            .order_by(FundamentalSnapshot.observed_at.desc())
        )
    )
    grouped: dict[tuple[int, str], list[FundamentalSnapshot]] = {}
    for row in rows:
        grouped.setdefault((row.source_id, row.metric), []).append(row)
    changes = []
    for pair in grouped.values():
        if len(pair) < 2:
            continue
        source = db.get(DataSource, pair[0].source_id)
        change = _make_change(
            instrument, pair[0], pair[1], category="fundamental", metric=pair[0].metric,
            period=pair[0].period_label, source=source, snapshot_type="fundamentals",
        )
        if change:
            changes.append(change)
    return changes


def detect_flow_changes(db: Session, instrument: Instrument) -> list[Change]:
    rows = list(
        db.scalars(
            select(FlowDaily)
            .where(FlowDaily.instrument_id == instrument.id)
            .order_by(FlowDaily.trading_date.desc())
        )
    )
    grouped: dict[tuple[int, str], list[FlowDaily]] = {}
    for row in rows:
        grouped.setdefault((row.source_id, row.flow_type), []).append(row)
    changes = []
    for pair in grouped.values():
        if len(pair) < 2:
            continue
        source = db.get(DataSource, pair[0].source_id)
        change = _make_change(
            instrument, pair[0], pair[1], category="flow", metric=pair[0].flow_type,
            period="1d", source=source, snapshot_type="flow_daily",
        )
        if change:
            changes.append(change)
    return changes
