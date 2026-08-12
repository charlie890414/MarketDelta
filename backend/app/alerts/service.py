from datetime import UTC, datetime, timedelta

import httpx
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


async def dispatch_alerts(
    deliveries: list[AlertDelivery],
    webhook_url: str | None,
    retries: int = 3,
    backoff_seconds: float = 1.0,
) -> None:
    if not deliveries or not webhook_url:
        return
    payload = {
        "event": "market_changes_alert",
        "deliveries": [
            {"delivery_id": delivery.id, "alert_id": delivery.alert_id, "change_id": delivery.change_id}
            for delivery in deliveries
        ],
    }
    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in range(max(1, retries)):
            try:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
                for delivery in deliveries:
                    delivery.status = "sent"
                return
            except httpx.HTTPError:
                if attempt + 1 < max(1, retries):
                    await asyncio.sleep(backoff_seconds * (2**attempt))
    for delivery in deliveries:
        delivery.status = "failed"
import asyncio
