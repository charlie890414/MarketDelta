from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import Change, DailyReport, Event, Instrument, Watchlist, WatchlistItem


def _number(value: Decimal | float | None) -> float | None:
    return float(value) if value is not None else None


def _change_payload(change: Change, instrument: Instrument) -> dict:
    return {
        "id": change.id,
        "symbol": instrument.symbol,
        "company_name": instrument.company_name,
        "market": instrument.market,
        "category": change.category,
        "metric": change.metric,
        "lookback": change.lookback,
        "direction": change.direction,
        "severity": change.severity,
        "total_score": change.total_score,
        "percentage_change": _number(change.percentage_change),
        "headline": change.metadata_.get("headline") if change.metadata_ else None,
    }


def _changes(db: Session, start: datetime, *, instrument_ids: set[int] | None = None):
    query = (
        select(Change, Instrument)
        .join(Instrument, Instrument.id == Change.instrument_id)
        .where(Change.detected_at >= start, Change.total_score >= 50)
        .order_by(desc(Change.total_score), desc(Change.detected_at))
    )
    if instrument_ids is not None:
        query = query.where(Change.instrument_id.in_(instrument_ids))
    return list(db.execute(query.limit(200)))


def _upsert_report(
    db: Session, report_date: date, report_type: str, title: str, payload: dict
) -> DailyReport:
    report = db.scalar(
        select(DailyReport).where(
            DailyReport.report_date == report_date,
            DailyReport.report_type == report_type,
        )
    )
    if report is None:
        report = DailyReport(
            report_date=report_date,
            report_type=report_type,
            title=title,
            payload=payload,
        )
        db.add(report)
    else:
        report.title = title
        report.payload = payload
    db.flush()
    return report


def generate_daily_reports(db: Session, report_date: date | None = None) -> list[DailyReport]:
    report_date = report_date or datetime.now(UTC).date()
    start = datetime.combine(report_date, datetime.min.time(), tzinfo=UTC) - timedelta(days=1)
    all_rows = _changes(db, start)
    all_changes = [_change_payload(change, instrument) for change, instrument in all_rows]

    portfolio_ids = set(
        db.scalars(
            select(WatchlistItem.instrument_id)
            .join(Watchlist, Watchlist.id == WatchlistItem.watchlist_id)
            .where(Watchlist.name == "Portfolio")
            .distinct()
        )
    )
    watchlist_ids = set(db.scalars(select(WatchlistItem.instrument_id).distinct()))
    portfolio_rows = _changes(db, start, instrument_ids=portfolio_ids)
    portfolio_changes = [_change_payload(change, instrument) for change, instrument in portfolio_rows]
    watchlist_rows = _changes(db, start, instrument_ids=watchlist_ids)
    watchlist_changes = [_change_payload(change, instrument) for change, instrument in watchlist_rows]

    upcoming = list(
        db.scalars(
            select(Event)
            .where(
                Event.event_date >= report_date,
                Event.event_date <= report_date + timedelta(days=14),
            )
            .order_by(Event.event_date, Event.title)
            .limit(100)
        )
    )
    catalysts = [
        {
            "id": event.id,
            "event_type": event.event_type,
            "title": event.title,
            "event_date": event.event_date.isoformat() if event.event_date else None,
            "source_url": event.source_url,
        }
        for event in upcoming
    ]

    reports = [
        _upsert_report(
            db,
            report_date,
            "market",
            "Market Changes Daily",
            {
                "important_changes": all_changes,
                "biggest_positive": [row for row in all_changes if row["direction"] == "up"][:5],
                "biggest_negative": [row for row in all_changes if row["direction"] == "down"][:5],
                "upcoming_catalysts": catalysts,
            },
        ),
        _upsert_report(
            db,
            report_date,
            "portfolio",
            "Portfolio Changes Daily",
            {"important_changes": portfolio_changes, "count": len(portfolio_changes)},
        ),
        _upsert_report(
            db,
            report_date,
            "watchlist",
            "Watchlist Changes Daily",
            {"important_changes": watchlist_changes, "count": len(watchlist_changes)},
        ),
    ]
    return reports
