from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Alert, AlertDelivery, Change, Instrument


def evaluate_alerts(db: Session, since: datetime | None = None) -> list[AlertDelivery]:
    since = since or datetime.now(UTC) - timedelta(days=1)
    changes = list(
        db.execute(
            select(Change, Instrument)
            .join(Instrument, Instrument.id == Change.instrument_id)
            .where(Change.detected_at >= since)
        )
    )
    deliveries: list[AlertDelivery] = []
    for alert in db.scalars(select(Alert).where(Alert.is_enabled.is_(True))):
        for change, instrument in changes:
            if change.total_score < alert.min_score:
                continue
            if alert.category and change.category != alert.category:
                continue
            if alert.market and instrument.market != alert.market:
                continue
            existing = db.scalar(
                select(AlertDelivery).where(
                    AlertDelivery.alert_id == alert.id,
                    AlertDelivery.change_id == change.id,
                )
            )
            if existing:
                continue
            delivery = AlertDelivery(alert_id=alert.id, change_id=change.id, status="pending")
            db.add(delivery)
            deliveries.append(delivery)
    db.flush()
    return deliveries
