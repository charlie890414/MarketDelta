from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import AIInterpretation, AIInterpretationChange, Change, Instrument


def generate_interpretation(db: Session, instrument: Instrument) -> AIInterpretation | None:
    changes = list(
        db.scalars(
            select(Change)
            .where(Change.instrument_id == instrument.id, Change.total_score >= 50)
            .order_by(desc(Change.total_score), desc(Change.detected_at))
            .limit(20)
        )
    )
    if not changes:
        return None

    positive = [change for change in changes if change.direction == "up"]
    negative = [change for change in changes if change.direction == "down"]
    supporting = [
        f"{change.metric} {change.direction} ({change.total_score:.0f}/100)"
        for change in positive[:5]
    ]
    contradictions = [
        f"{change.metric} moved {change.direction}"
        for change in negative[:5]
    ]
    summary = (
        f"{instrument.symbol} has {len(changes)} material deterministic changes, "
        f"with {len(positive)} positive and {len(negative)} negative signals."
    )
    impact = "strengthened" if len(positive) > len(negative) else "weakened" if negative else "unknown"
    interpretation = AIInterpretation(
        instrument_id=instrument.id,
        interpretation_type="change",
        summary=summary,
        why_it_matters="This is a rule-based synthesis of scored changes, not a prediction.",
        supporting_signals=supporting,
        contradictions=contradictions,
        watch_next=["Review the next scheduled event", "Check whether the highest-score signal persists"],
        thesis_impact=impact,
        model_provider="deterministic",
        model_name="rule-based-v1",
        prompt_version="none",
        generated_at=datetime.now(UTC),
        metadata_={"source": "changes", "change_count": len(changes)},
    )
    db.add(interpretation)
    db.flush()
    db.add_all(
        [
            AIInterpretationChange(interpretation_id=interpretation.id, change_id=change.id)
            for change in changes
        ]
    )
    db.flush()
    return interpretation
