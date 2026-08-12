"""Grounded daily briefing derived only from persisted changes and events."""

from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Change, DailyReport, Event, Instrument


def _upsert(db: Session, report_date: date, payload: dict) -> DailyReport:
    report = db.scalar(
        select(DailyReport).where(
            DailyReport.report_date == report_date, DailyReport.report_type == "ai_market"
        )
    )
    if report is None:
        report = DailyReport(
            report_date=report_date,
            report_type="ai_market",
            title="AI Market Brief",
            payload=payload,
        )
        db.add(report)
    else:
        report.title = "AI Market Brief"
        report.payload = payload
    db.flush()
    return report


def _signal(change: Change, instrument: Instrument) -> dict:
    return {
        "change_id": change.id,
        "symbol": instrument.symbol,
        "metric": change.metric,
        "direction": change.direction,
        "score": round(change.total_score, 1),
        "category": change.category,
    }


def _deterministic_summary(signals: list[dict], events: list[dict]) -> str:
    if not signals:
        return "No material, persisted market changes were detected in the selected window."
    lead = signals[0]
    return (
        f"The highest-priority signal is {lead['symbol']} {lead['metric']} "
        f"({lead['direction']}, score {lead['score']}). "
        f"{len(events)} upcoming catalysts require monitoring."
    )


def _llm_summary(signals: list[dict], events: list[dict]) -> str | None:
    settings = get_settings()
    if not settings.llm_base_url or not settings.llm_api_key:
        return None
    try:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": settings.llm_model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Write a concise market brief from supplied signals only. Do not predict prices "
                            "or recommend trades. Cite change ids in square brackets for every claim."
                        ),
                    },
                    {"role": "user", "content": f"Signals: {signals}\nUpcoming events: {events}"},
                ],
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return None


def generate_ai_daily_brief(db: Session, report_date: date | None = None) -> DailyReport:
    report_date = report_date or datetime.now(UTC).date()
    since = datetime.combine(report_date, datetime.min.time(), tzinfo=UTC) - timedelta(days=1)
    rows = list(
        db.execute(
            select(Change, Instrument)
            .join(Instrument, Instrument.id == Change.instrument_id)
            .where(Change.detected_at >= since, Change.total_score >= 50)
            .order_by(desc(Change.total_score), desc(Change.detected_at))
            .limit(12)
        )
    )
    signals = [_signal(change, instrument) for change, instrument in rows]
    event_rows = list(
        db.scalars(
            select(Event)
            .where(
                Event.event_date >= report_date,
                Event.event_date <= report_date + timedelta(days=14),
            )
            .order_by(Event.event_date, Event.title)
            .limit(12)
        )
    )
    events = [
        {
            "event_id": event.id,
            "title": event.title,
            "date": event.event_date.isoformat() if event.event_date else None,
        }
        for event in event_rows
    ]
    llm_summary = _llm_summary(signals, events)
    return _upsert(
        db,
        report_date,
        {
            "summary": llm_summary or _deterministic_summary(signals, events),
            "signals": signals,
            "upcoming_catalysts": events,
            "evidence": [{"type": "change", "id": row["change_id"]} for row in signals],
            "model_provider": "openai-compatible" if llm_summary else "deterministic",
            "data_boundary": "Persisted changes and events only; not investment advice.",
        },
    )
