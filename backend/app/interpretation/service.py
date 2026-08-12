from datetime import UTC, datetime

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AIInterpretation, AIInterpretationChange, Change, Instrument

PROMPT_VERSION = "change-interpretation-v1"


class InterpretationOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    why_it_matters: str = Field(min_length=1, max_length=4000)
    supporting_signals: list[str] = Field(default_factory=list, max_length=10)
    contradictions: list[str] = Field(default_factory=list, max_length=10)
    watch_next: list[str] = Field(default_factory=list, max_length=10)
    thesis_impact: str = Field(pattern="^(strengthened|weakened|mixed|unknown)$")


def _deterministic_output(instrument: Instrument, changes: list[Change]) -> InterpretationOutput:
    positive = [change for change in changes if change.direction == "up"]
    negative = [change for change in changes if change.direction == "down"]
    return InterpretationOutput(
        summary=(
            f"{instrument.symbol} has {len(changes)} material deterministic changes, "
            f"with {len(positive)} positive and {len(negative)} negative signals."
        ),
        why_it_matters="This is a rule-based synthesis of scored changes, not a prediction.",
        supporting_signals=[
            f"{change.metric} {change.direction} ({change.total_score:.0f}/100)"
            for change in positive[:5]
        ],
        contradictions=[f"{change.metric} moved {change.direction}" for change in negative[:5]],
        watch_next=["Review the next scheduled event", "Check whether the highest-score signal persists"],
        thesis_impact="strengthened" if len(positive) > len(negative) else "weakened" if negative else "unknown",
    )


def _llm_output(instrument: Instrument, changes: list[Change]) -> InterpretationOutput | None:
    settings = get_settings()
    if not settings.llm_base_url or not settings.llm_api_key:
        return None
    signals = [
        {
            "category": change.category,
            "metric": change.metric,
            "period": change.period,
            "direction": change.direction,
            "percentage_change": change.percentage_change,
            "score": change.total_score,
        }
        for change in changes
    ]
    payload = {
        "model": settings.llm_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You summarize objective market signals. Do not invent facts or predict prices. "
                    "Return only JSON with keys: summary, why_it_matters, supporting_signals, "
                    "contradictions, watch_next, thesis_impact. thesis_impact must be one of "
                    "strengthened, weakened, mixed, unknown."
                ),
            },
            {
                "role": "user",
                "content": f"Instrument: {instrument.symbol} ({instrument.company_name})\nSignals: {signals}",
            },
        ],
    }
    try:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=payload,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return InterpretationOutput.model_validate_json(content)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValidationError, ValueError):
        return None


def generate_interpretation(db: Session, instrument: Instrument) -> AIInterpretation | None:
    settings = get_settings()
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

    output = _llm_output(instrument, changes) or _deterministic_output(instrument, changes)
    model_provider = "openai-compatible" if settings.llm_base_url and settings.llm_api_key else "deterministic"
    model_name = settings.llm_model if model_provider != "deterministic" else "rule-based-v1"
    interpretation = AIInterpretation(
        instrument_id=instrument.id,
        interpretation_type="change",
        summary=output.summary,
        why_it_matters=output.why_it_matters,
        supporting_signals=output.supporting_signals,
        contradictions=output.contradictions,
        watch_next=output.watch_next,
        thesis_impact=output.thesis_impact,
        model_provider=model_provider,
        model_name=model_name,
        prompt_version=PROMPT_VERSION if model_provider != "deterministic" else "none",
        generated_at=datetime.now(UTC),
        metadata_={"source": "changes", "change_count": len(changes), "llm_enabled": model_provider != "deterministic"},
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
