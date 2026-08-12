from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("market", "symbol"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    exchange: Mapped[str | None] = mapped_column(String(32))
    company_name: Mapped[str] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(8))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InstrumentAlias(Base):
    __tablename__ = "instrument_aliases"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String(255), index=True)
    alias_type: Mapped[str] = mapped_column(String(32), default="name")
    provider: Mapped[str | None] = mapped_column(String(64))


class Watchlist(Base):
    __tablename__ = "watchlists"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "instrument_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"))
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer, default=0)


class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    source_type: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[str] = mapped_column(String(16))
    is_enabled: Mapped[bool] = mapped_column(default=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class RawIngestion(Base):
    __tablename__ = "raw_ingestions"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    provider_endpoint: Mapped[str | None] = mapped_column(String(255))
    request_key: Mapped[str | None] = mapped_column(String(255))
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    source_data_date: Mapped[date | None] = mapped_column(Date)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    content_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    payload: Mapped[dict | list | None] = mapped_column(JSONB)
    raw_text: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(String(128), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), index=True)
    items_requested: Mapped[int] = mapped_column(default=0)
    items_fetched: Mapped[int] = mapped_column(default=0)
    items_inserted: Mapped[int] = mapped_column(default=0)
    items_changed: Mapped[int] = mapped_column(default=0)
    items_failed: Mapped[int] = mapped_column(default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)


class PriceDaily(Base):
    __tablename__ = "price_daily"
    __table_args__ = (UniqueConstraint("instrument_id", "trading_date", "source_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    raw_ingestion_id: Mapped[int | None] = mapped_column(ForeignKey("raw_ingestions.id"))
    trading_date: Mapped[date] = mapped_column(Date)
    close: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))


class FlowDaily(Base):
    __tablename__ = "flow_daily"
    __table_args__ = (
        UniqueConstraint("instrument_id", "source_id", "trading_date", "flow_type"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    raw_ingestion_id: Mapped[int | None] = mapped_column(ForeignKey("raw_ingestions.id"))
    trading_date: Mapped[date] = mapped_column(Date)
    flow_type: Mapped[str] = mapped_column(String(32))
    net_volume: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    unit: Mapped[str] = mapped_column(String(16), default="shares")


class OwnershipSnapshot(Base):
    __tablename__ = "ownership_snapshots"
    __table_args__ = (
        UniqueConstraint("instrument_id", "source_id", "snapshot_date", "holder_bucket"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    raw_ingestion_id: Mapped[int | None] = mapped_column(ForeignKey("raw_ingestions.id"))
    snapshot_date: Mapped[date] = mapped_column(Date)
    holder_bucket: Mapped[str] = mapped_column(String(64))
    holder_count: Mapped[int | None] = mapped_column()
    share_count: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    ownership_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EstimateSnapshot(Base):
    __tablename__ = "estimate_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "source_id", "metric", "fiscal_period_label", "observed_at"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    raw_ingestion_id: Mapped[int | None] = mapped_column(ForeignKey("raw_ingestions.id"))
    metric: Mapped[str] = mapped_column(String(64))
    fiscal_period_label: Mapped[str] = mapped_column(String(32))
    value: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    unit: Mapped[str] = mapped_column(String(32))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FundamentalSnapshot(Base):
    __tablename__ = "fundamentals"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "source_id", "metric", "period_label", "observed_at"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    raw_ingestion_id: Mapped[int | None] = mapped_column(ForeignKey("raw_ingestions.id"))
    metric: Mapped[str] = mapped_column(String(64))
    period_label: Mapped[str] = mapped_column(String(32))
    value: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    unit: Mapped[str] = mapped_column(String(32))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    raw_ingestion_id: Mapped[int | None] = mapped_column(ForeignKey("raw_ingestions.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    event_date: Mapped[date | None] = mapped_column(Date)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    importance: Mapped[str | None] = mapped_column(String(16))
    external_id: Mapped[str | None] = mapped_column(String(255))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NewsItem(Base):
    __tablename__ = "news_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    raw_ingestion_id: Mapped[int | None] = mapped_column(ForeignKey("raw_ingestions.id"))
    external_id: Mapped[str | None] = mapped_column(String(255))
    headline: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_name: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64))
    importance_score: Mapped[float | None] = mapped_column()
    is_material: Mapped[bool | None] = mapped_column(Boolean)
    summary: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NewsInstrument(Base):
    __tablename__ = "news_instruments"
    news_item_id: Mapped[int] = mapped_column(
        ForeignKey("news_items.id", ondelete="CASCADE"), primary_key=True
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    relevance_score: Mapped[float | None] = mapped_column()


class Change(Base):
    __tablename__ = "changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    metric: Mapped[str] = mapped_column(String(64))
    period: Mapped[str | None] = mapped_column(String(32))
    lookback: Mapped[str | None] = mapped_column(String(32))
    baseline_type: Mapped[str] = mapped_column(String(32))
    previous_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8))
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8))
    absolute_change: Mapped[Decimal | None] = mapped_column(Numeric(30, 8))
    percentage_change: Mapped[float | None] = mapped_column()
    direction: Mapped[str] = mapped_column(String(16))
    change_type: Mapped[str] = mapped_column(String(32))
    magnitude_score: Mapped[float] = mapped_column()
    rarity_score: Mapped[float] = mapped_column()
    relevance_score: Mapped[float] = mapped_column()
    freshness_score: Mapped[float] = mapped_column()
    source_quality_score: Mapped[float] = mapped_column()
    total_score: Mapped[float] = mapped_column(index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"))
    previous_snapshot_id: Mapped[int | None] = mapped_column()
    current_snapshot_id: Mapped[int | None] = mapped_column()
    previous_snapshot_type: Mapped[str | None] = mapped_column(String(64))
    current_snapshot_type: Mapped[str | None] = mapped_column(String(64))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class AIInterpretation(Base):
    __tablename__ = "ai_interpretations"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    interpretation_type: Mapped[str] = mapped_column(String(32), default="change")
    summary: Mapped[str] = mapped_column(Text)
    why_it_matters: Mapped[str | None] = mapped_column(Text)
    supporting_signals: Mapped[list] = mapped_column(JSONB, default=list)
    contradictions: Mapped[list] = mapped_column(JSONB, default=list)
    watch_next: Mapped[list] = mapped_column(JSONB, default=list)
    thesis_impact: Mapped[str | None] = mapped_column(String(32))
    model_provider: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class AIInterpretationChange(Base):
    __tablename__ = "ai_interpretation_changes"
    interpretation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_interpretations.id", ondelete="CASCADE"), primary_key=True
    )
    change_id: Mapped[int] = mapped_column(
        ForeignKey("changes.id", ondelete="CASCADE"), primary_key=True
    )


class DailyReport(Base):
    __tablename__ = "daily_reports"
    __table_args__ = (UniqueConstraint("report_date", "report_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    report_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    min_score: Mapped[float] = mapped_column(default=85)
    category: Mapped[str | None] = mapped_column(String(32))
    market: Mapped[str | None] = mapped_column(String(16))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"
    __table_args__ = (UniqueConstraint("alert_id", "change_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"))
    change_id: Mapped[int] = mapped_column(ForeignKey("changes.id", ondelete="CASCADE"))
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(32), default="pending")
