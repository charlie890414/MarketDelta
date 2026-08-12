from datetime import UTC, datetime
from math import pow

from app.domain.observations import ChangeCandidate

WEIGHTS = {
    "magnitude": 0.30,
    "rarity": 0.20,
    "relevance": 0.25,
    "freshness": 0.15,
    "source_quality": 0.10,
}

NEWS_FRESHNESS_HALF_LIFE_DAYS = 3


def freshness_score(category: str, observed_at: datetime, *, now: datetime | None = None) -> float:
    """Return a 0–100 freshness score, with news decaying by its publication age."""
    now = now or datetime.now(UTC)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    age_days = max((now - observed_at).total_seconds() / 86400, 0)
    if category == "news":
        return round(100 * pow(0.5, age_days / NEWS_FRESHNESS_HALF_LIFE_DAYS), 2)
    return max(0, min(100, 100 - age_days * 10))


def severity(score: float) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "important"
    if score >= 50:
        return "notable"
    if score >= 30:
        return "minor"
    return "noise"


def score_change(
    candidate: ChangeCandidate,
    *,
    rarity: float = 50,
    freshness: float = 100,
    source_quality: float = 80,
) -> dict[str, float | str]:
    if candidate.change_type == "new":
        magnitude = {"event": 65, "news": 60}.get(candidate.category, 50)
    else:
        magnitude = min(abs(candidate.percentage_change or 0) * 8, 100)
    relevance = {
        "expectation": 95,
        "fundamental": 90,
        "event": 80,
        "news": 70,
        "flow": 75,
        "price": 55,
    }.get(candidate.category, 50)
    total = sum(
        value * WEIGHTS[key]
        for key, value in {
            "magnitude": magnitude,
            "rarity": rarity,
            "relevance": relevance,
            "freshness": freshness,
            "source_quality": source_quality,
        }.items()
    )
    total = round(max(0, min(100, total)), 2)
    return {
        "magnitude": magnitude,
        "rarity": rarity,
        "relevance": relevance,
        "freshness": freshness,
        "source_quality": source_quality,
        "total": total,
        "severity": severity(total),
    }
