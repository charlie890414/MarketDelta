import json
from datetime import UTC, datetime
from decimal import Decimal
from itertools import pairwise
from statistics import pstdev
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.changes.comparator import compare
from app.config import get_settings
from app.db.models import (
    Change,
    DataSource,
    EstimateSnapshot,
    Event,
    FlowDaily,
    FundamentalSnapshot,
    Instrument,
    NewsInstrument,
    NewsItem,
    OwnershipSnapshot,
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
    lookback: str = "previous",
    rarity: float = 50,
    value_getter=None,
    change_type: str = "changed",
) -> Change | None:
    if value_getter:
        current_value = value_getter(current)
        previous_value = value_getter(previous)
    else:
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
        baseline_type=lookback,
    )
    observed_at = current.observed_at if hasattr(current, "observed_at") else datetime.combine(
        current.trading_date, datetime.min.time(), tzinfo=UTC
    )
    age_days = max((datetime.now(UTC) - observed_at).total_seconds() / 86400, 0)
    scores = score_change(
        candidate,
        rarity=rarity,
        freshness=max(0, min(100, 100 - age_days * 10)),
        source_quality=_source_quality(source),
    )
    return Change(
        instrument_id=instrument.id,
        category=category,
        metric=metric,
        period=period,
        baseline_type=lookback,
        lookback=lookback,
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


def _rarity(rows, value_getter) -> float:
    """Return the percentile of the latest move among historical adjacent moves."""
    if len(rows) < 3:
        return 50
    moves: list[float] = []
    for current, previous in pairwise(rows):
        current_value = Decimal(str(value_getter(current)))
        previous_value = Decimal(str(value_getter(previous)))
        if previous_value == 0:
            continue
        moves.append(float(abs((current_value - previous_value) / previous_value) * 100))
    if not moves:
        return 50
    latest = moves[0]
    return round(sum(move <= latest for move in moves) / len(moves) * 100, 2)


def detect_price_changes(db: Session, instrument: Instrument) -> list[Change]:
    rows = list(
        db.scalars(
            select(PriceDaily)
            .where(PriceDaily.instrument_id == instrument.id)
            .order_by(PriceDaily.trading_date.desc())
        )
    )
    if len(rows) < 2:
        return []
    source = db.get(DataSource, rows[0].source_id)
    changes = []
    for lookback, index in (("previous", 1), ("5d", 5), ("20d", 20)):
        if len(rows) <= index:
            continue
        change = _make_change(
            instrument,
            rows[0],
            rows[index],
            category="price",
            metric="close",
            period=lookback,
            source=source,
            snapshot_type="price_daily",
            lookback=lookback,
            rarity=_rarity(rows, lambda row: row.close),
        )
        if change:
            changes.append(change)
    if rows[0].volume is not None and rows[1].volume is not None:
        volume_change = _make_change(
            instrument,
            rows[0],
            rows[1],
            category="price",
            metric="volume",
            period="1d",
            source=source,
            snapshot_type="price_daily",
            value_getter=lambda row: row.volume,
            rarity=_rarity(rows, lambda row: row.volume or 0),
        )
        if volume_change:
            changes.append(volume_change)
        average_volume = sum((row.volume or 0 for row in rows[1:21]), Decimal(0)) / min(len(rows[1:21]), 20)
        relative_volume = _make_change(
            instrument,
            SimpleNamespace(
                value=rows[0].volume,
                source_id=rows[0].source_id,
                id=rows[0].id,
                trading_date=rows[0].trading_date,
            ),
            SimpleNamespace(
                value=average_volume,
                source_id=rows[1].source_id,
                id=rows[1].id,
                trading_date=rows[1].trading_date,
            ),
            category="price",
            metric="relative_volume",
            period="20d",
            source=source,
            snapshot_type="price_daily",
            lookback="20d",
            value_getter=lambda row: row.value,
        )
        if relative_volume:
            changes.append(relative_volume)
    if len(rows) >= 21:
        current_volatility = Decimal(str(pstdev(float(row.close) for row in rows[:5])))
        previous_volatility = Decimal(str(pstdev(float(row.close) for row in rows[5:10])))
        volatility_change = _make_change(
            instrument,
            SimpleNamespace(
                value=current_volatility,
                source_id=rows[0].source_id,
                id=rows[0].id,
                trading_date=rows[0].trading_date,
            ),
            SimpleNamespace(
                value=previous_volatility,
                source_id=rows[1].source_id,
                id=rows[1].id,
                trading_date=rows[1].trading_date,
            ),
            category="price",
            metric="volatility",
            period="5d",
            source=source,
            snapshot_type="price_daily",
            lookback="5d",
        )
        if volatility_change:
            changes.append(volatility_change)

        prior_high = max(row.close for row in rows[1:21])
        if rows[0].close >= prior_high:
            breakout_change = _make_change(
                instrument,
                SimpleNamespace(
                    value=rows[0].close,
                    source_id=rows[0].source_id,
                    id=rows[0].id,
                    trading_date=rows[0].trading_date,
                ),
                SimpleNamespace(
                    value=prior_high,
                    source_id=rows[1].source_id,
                    id=rows[1].id,
                    trading_date=rows[1].trading_date,
                ),
                category="price",
                metric="breakout",
                period="20d",
                source=source,
                snapshot_type="price_daily",
                lookback="20d",
                change_type="breakout",
            )
            if breakout_change:
                changes.append(breakout_change)
        drawdown_change = _make_change(
            instrument,
            SimpleNamespace(
                value=rows[0].close,
                source_id=rows[0].source_id,
                id=rows[0].id,
                trading_date=rows[0].trading_date,
            ),
            SimpleNamespace(
                value=prior_high,
                source_id=rows[1].source_id,
                id=rows[1].id,
                trading_date=rows[1].trading_date,
            ),
            category="price",
            metric="drawdown",
            period="20d",
            source=source,
            snapshot_type="price_daily",
            lookback="20d",
        )
        if drawdown_change and drawdown_change.direction == "down":
            changes.append(drawdown_change)
    benchmark_symbols = json.loads(get_settings().benchmark_symbols)
    benchmark_symbol = benchmark_symbols.get(instrument.market)
    benchmark = (
        db.scalar(
            select(Instrument).where(
                Instrument.market == instrument.market,
                Instrument.symbol == benchmark_symbol,
            )
        )
        if benchmark_symbol
        else None
    )
    if benchmark and benchmark.id != instrument.id:
        benchmark_rows = list(
            db.scalars(
                select(PriceDaily)
                .where(PriceDaily.instrument_id == benchmark.id)
                .order_by(PriceDaily.trading_date.desc())
            )
        )
        by_date = {row.trading_date: row for row in benchmark_rows}
        for lookback, index in (("previous", 1), ("5d", 5), ("20d", 20)):
            if len(rows) <= index:
                continue
            benchmark_current = by_date.get(rows[0].trading_date)
            benchmark_previous = by_date.get(rows[index].trading_date)
            if not benchmark_current or not benchmark_previous:
                continue
            instrument_ratio = rows[0].close / rows[index].close
            benchmark_ratio = benchmark_current.close / benchmark_previous.close
            current_relative = Decimal(100) * instrument_ratio
            previous_relative = Decimal(100) * benchmark_ratio
            relative_change = _make_change(
                instrument,
                SimpleNamespace(
                    value=current_relative,
                    source_id=rows[0].source_id,
                    id=rows[0].id,
                    trading_date=rows[0].trading_date,
                ),
                SimpleNamespace(
                    value=previous_relative,
                    source_id=rows[index].source_id,
                    id=rows[index].id,
                    trading_date=rows[index].trading_date,
                ),
                category="price",
                metric="benchmark_relative_return",
                period=lookback,
                source=source,
                snapshot_type="price_daily",
                lookback=lookback,
                rarity=50,
            )
            if relative_change:
                relative_change.metadata_ = {"benchmark_symbol": benchmark.symbol}
                changes.append(relative_change)
    return changes


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
            period=pair[0].fiscal_period_label,
            source=source,
            snapshot_type="estimate_snapshots",
            rarity=_rarity(pair, lambda row: row.value),
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
    grouped: dict[tuple[int, str, str], list[FundamentalSnapshot]] = {}
    for row in rows:
        grouped.setdefault((row.source_id, row.metric, row.period_label), []).append(row)
    changes = []
    for pair in grouped.values():
        if len(pair) < 2:
            continue
        source = db.get(DataSource, pair[0].source_id)
        change = _make_change(
            instrument, pair[0], pair[1], category="fundamental", metric=pair[0].metric,
            period=pair[0].period_label,
            source=source,
            snapshot_type="fundamentals",
            rarity=_rarity(pair, lambda row: row.value),
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
        for lookback, index in (("previous", 1), ("5d", 5), ("20d", 20)):
            if len(pair) <= index or (index > 1 and len(pair) < index * 2):
                continue
            if index > 1:
                current_value = sum((row.net_volume for row in pair[:index]), Decimal(0))
                previous_value = sum((row.net_volume for row in pair[index : index * 2]), Decimal(0))
                current = SimpleNamespace(
                    value=current_value,
                    source_id=pair[0].source_id,
                    id=pair[0].id,
                    trading_date=pair[0].trading_date,
                )
                previous = SimpleNamespace(
                    value=previous_value,
                    source_id=pair[index].source_id,
                    id=pair[index].id,
                    trading_date=pair[index].trading_date,
                )
            else:
                current, previous = pair[0], pair[index]
            change = _make_change(
                instrument,
                current,
                previous,
                category="flow",
                metric=pair[0].flow_type,
                period=lookback,
                source=source,
                snapshot_type="flow_daily",
                lookback=lookback,
                rarity=_rarity(pair, lambda row: row.net_volume),
            )
            if change:
                changes.append(change)
    return changes


def detect_ownership_changes(db: Session, instrument: Instrument) -> list[Change]:
    rows = list(
        db.scalars(
            select(OwnershipSnapshot)
            .where(OwnershipSnapshot.instrument_id == instrument.id)
            .order_by(OwnershipSnapshot.snapshot_date.desc())
        )
    )
    grouped: dict[tuple[int, str], list[OwnershipSnapshot]] = {}
    for row in rows:
        grouped.setdefault((row.source_id, row.holder_bucket), []).append(row)

    changes: list[Change] = []
    for pair in grouped.values():
        if len(pair) < 2:
            continue
        current, previous = pair[:2]
        getter = (
            (lambda row: row.ownership_pct)
            if current.ownership_pct is not None and previous.ownership_pct is not None
            else (lambda row: row.share_count)
            if current.share_count is not None and previous.share_count is not None
            else lambda row: Decimal(row.holder_count or 0)
        )
        change = _make_change(
            instrument,
            current,
            previous,
            category="ownership",
            metric=f"holder_{current.holder_bucket}",
            period="previous",
            source=db.get(DataSource, current.source_id),
            snapshot_type="ownership_snapshots",
            value_getter=getter,
            rarity=_rarity(pair, getter),
        )
        if change:
            change.metadata_ = {"holder_bucket": current.holder_bucket}
            changes.append(change)
    return changes


def detect_event_changes(db: Session, instrument: Instrument) -> list[Change]:
    rows = list(
        db.scalars(
            select(Event)
            .where(Event.instrument_id == instrument.id)
            .order_by(Event.event_date.desc(), Event.id.desc())
        )
    )
    source_by_id = {source.id: source for source in db.scalars(select(DataSource))}
    changes: list[Change] = []
    for event in rows:
        current = SimpleNamespace(
            value=Decimal(1),
            source_id=event.source_id,
            id=event.id,
            observed_at=datetime.combine(
                event.event_date or datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC
            ),
        )
        previous = SimpleNamespace(value=Decimal(0), source_id=event.source_id, id=0)
        change = _make_change(
            instrument,
            current,
            previous,
            category="event",
            metric=event.event_type,
            period=event.event_date.isoformat() if event.event_date else None,
            source=source_by_id.get(event.source_id),
            snapshot_type="events",
            change_type="new",
        )
        if change:
            change.metadata_ = {"event_id": event.id, "title": event.title, "source_url": event.source_url}
            changes.append(change)
    return changes


def detect_news_changes(db: Session, instrument: Instrument) -> list[Change]:
    rows = list(
        db.scalars(
            select(NewsItem)
            .join(NewsInstrument, NewsInstrument.news_item_id == NewsItem.id)
            .where(NewsInstrument.instrument_id == instrument.id)
            .order_by(NewsItem.published_at.desc(), NewsItem.id.desc())
        )
    )
    changes: list[Change] = []
    for news in rows:
        importance = Decimal(str(news.importance_score if news.importance_score else 1))
        current = SimpleNamespace(
            value=importance,
            source_id=news.source_id,
            id=news.id,
            observed_at=news.published_at,
        )
        previous = SimpleNamespace(value=Decimal(0), source_id=news.source_id, id=0)
        change = _make_change(
            instrument,
            current,
            previous,
            category="news",
            metric=news.category or "headline",
            period="new",
            source=db.get(DataSource, news.source_id),
            snapshot_type="news_items",
            change_type="new",
        )
        if change:
            change.metadata_ = {
                "news_id": news.id,
                "headline": news.headline,
                "source_url": news.source_url,
                "is_material": news.is_material,
            }
            changes.append(change)
    return changes
