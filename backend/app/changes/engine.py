from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.changes.comparator import compare
from app.db.models import Change, EstimateSnapshot, Instrument, PriceDaily
from app.domain.observations import ChangeCandidate
from app.scoring.scorer import score_change


def detect_price_changes(db: Session, instrument: Instrument) -> list[Change]:
    rows = list(
        db.scalars(
            select(PriceDaily)
            .where(PriceDaily.instrument_id == instrument.id)
            .order_by(PriceDaily.trading_date.desc())
            .limit(2)
        )
    )
    if len(rows) < 2 or rows[0].close == rows[1].close:
        return []
    current, previous = rows[0], rows[1]
    absolute, pct, direction = compare(previous.close, current.close)
    candidate = ChangeCandidate(
        symbol=instrument.symbol,
        market=instrument.market,
        category="price",
        metric="close",
        period="1d",
        previous=previous.close,
        current=current.close,
        absolute_change=absolute,
        percentage_change=pct,
        direction=direction,
        change_type="changed",
        baseline_type="previous",
    )
    scores = score_change(candidate)
    return [
        Change(
            instrument_id=instrument.id,
            category=candidate.category,
            metric=candidate.metric,
            period=candidate.period,
            baseline_type=candidate.baseline_type,
            previous_value=previous.close,
            current_value=current.close,
            absolute_change=absolute,
            percentage_change=pct,
            direction=direction,
            change_type="changed",
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
            detected_at=datetime.now(UTC),
            metadata_={},
        )
    ]


def detect_estimate_changes(db: Session, instrument: Instrument) -> list[Change]:
    rows = list(
        db.scalars(
            select(EstimateSnapshot)
            .where(EstimateSnapshot.instrument_id == instrument.id)
            .order_by(EstimateSnapshot.observed_at.desc())
            .limit(2)
        )
    )
    if len(rows) < 2 or rows[0].value == rows[1].value:
        return []
    current, previous = rows[0], rows[1]
    absolute, pct, direction = compare(previous.value, current.value)
    candidate = ChangeCandidate(
        symbol=instrument.symbol,
        market=instrument.market,
        category="expectation",
        metric=current.metric,
        period=current.fiscal_period_label,
        previous=previous.value,
        current=current.value,
        absolute_change=absolute,
        percentage_change=pct,
        direction=direction,
        change_type="changed",
        baseline_type="previous",
    )
    scores = score_change(candidate, rarity=70)
    return [
        Change(
            instrument_id=instrument.id,
            category=candidate.category,
            metric=candidate.metric,
            period=candidate.period,
            baseline_type=candidate.baseline_type,
            previous_value=previous.value,
            current_value=current.value,
            absolute_change=absolute,
            percentage_change=pct,
            direction=direction,
            change_type="changed",
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
            detected_at=datetime.now(UTC),
            metadata_={},
        )
    ]
