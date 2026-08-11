"""initial market changes schema"""
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Column as SAColumn,
)

from alembic import op


# Keep the migration compact while using SQLAlchemy constructs with Alembic.
def Column(name, *args, **kwargs):
    if args and isinstance(args[0], ForeignKey):
        return SAColumn(name, BigInteger, *args, **kwargs)
    return SAColumn(name, *args, **kwargs)


op.Column = Column
op.ForeignKey = ForeignKey

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("data_sources", op.Column("id", BigInteger, primary_key=True), op.Column("code", String(64), nullable=False, unique=True), op.Column("name", String(128), nullable=False), op.Column("source_type", String(32), nullable=False), op.Column("confidence", String(16), nullable=False), op.Column("is_enabled", Boolean, nullable=False, server_default="true"), op.Column("metadata", JSON, nullable=False))
    op.create_table("instruments", op.Column("id", BigInteger, primary_key=True), op.Column("symbol", String(32), nullable=False), op.Column("market", String(16), nullable=False), op.Column("exchange", String(32)), op.Column("company_name", String(255), nullable=False), op.Column("currency", String(8), nullable=False), op.Column("is_active", Boolean, nullable=False, server_default="true"), op.Column("created_at", DateTime(timezone=True)), op.Column("updated_at", DateTime(timezone=True)), UniqueConstraint("market", "symbol"))
    op.create_table("instrument_aliases", op.Column("id", BigInteger, primary_key=True), op.Column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False), op.Column("alias", String(255), nullable=False), op.Column("alias_type", String(32), nullable=False), op.Column("provider", String(64)))
    op.create_table("watchlists", op.Column("id", BigInteger, primary_key=True), op.Column("name", String(128), nullable=False, unique=True), op.Column("description", Text))
    op.create_table("watchlist_items", op.Column("id", BigInteger, primary_key=True), op.Column("watchlist_id", ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False), op.Column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False), op.Column("priority", Integer, nullable=False, server_default="0"), UniqueConstraint("watchlist_id", "instrument_id"))
    op.create_table("raw_ingestions", op.Column("id", BigInteger, primary_key=True), op.Column("source_id", ForeignKey("data_sources.id"), nullable=False), op.Column("provider_endpoint", String(255)), op.Column("request_key", String(255)), op.Column("instrument_id", ForeignKey("instruments.id")), op.Column("source_data_date", Date), op.Column("fetched_at", DateTime(timezone=True), nullable=False), op.Column("http_status", Integer), op.Column("status", String(32), nullable=False), op.Column("content_hash", String(128)), op.Column("payload", JSON), op.Column("raw_text", Text), op.Column("metadata", JSON, nullable=False))
    op.create_table("job_runs", op.Column("id", BigInteger, primary_key=True), op.Column("job_name", String(128), nullable=False), op.Column("source_id", ForeignKey("data_sources.id")), op.Column("started_at", DateTime(timezone=True), nullable=False), op.Column("finished_at", DateTime(timezone=True)), op.Column("status", String(32), nullable=False), op.Column("items_requested", Integer, nullable=False, server_default="0"), op.Column("items_fetched", Integer, nullable=False, server_default="0"), op.Column("items_inserted", Integer, nullable=False, server_default="0"), op.Column("items_changed", Integer, nullable=False, server_default="0"), op.Column("items_failed", Integer, nullable=False, server_default="0"), op.Column("error_summary", Text))
    op.create_table("fundamentals", op.Column("id", BigInteger, primary_key=True), op.Column("instrument_id", ForeignKey("instruments.id"), nullable=False), op.Column("source_id", ForeignKey("data_sources.id"), nullable=False), op.Column("raw_ingestion_id", ForeignKey("raw_ingestions.id")), op.Column("metric", String(64), nullable=False), op.Column("period_label", String(32), nullable=False), op.Column("value", Numeric(30, 8), nullable=False), op.Column("unit", String(32), nullable=False), op.Column("observed_at", DateTime(timezone=True), nullable=False))
    op.create_table("flow_daily", op.Column("id", BigInteger, primary_key=True), op.Column("instrument_id", ForeignKey("instruments.id"), nullable=False), op.Column("source_id", ForeignKey("data_sources.id"), nullable=False), op.Column("raw_ingestion_id", ForeignKey("raw_ingestions.id")), op.Column("trading_date", Date, nullable=False), op.Column("flow_type", String(32), nullable=False), op.Column("net_volume", Numeric(30, 4), nullable=False), op.Column("unit", String(16), nullable=False))
    op.create_table("events", op.Column("id", BigInteger, primary_key=True), op.Column("instrument_id", ForeignKey("instruments.id")), op.Column("source_id", ForeignKey("data_sources.id"), nullable=False), op.Column("raw_ingestion_id", ForeignKey("raw_ingestions.id")), op.Column("event_type", String(64), nullable=False), op.Column("title", Text, nullable=False), op.Column("event_date", Date), op.Column("source_url", Text), op.Column("status", String(32), nullable=False, server_default="scheduled"))
    op.create_table("price_daily", op.Column("id", BigInteger, primary_key=True), op.Column("instrument_id", ForeignKey("instruments.id"), nullable=False), op.Column("source_id", ForeignKey("data_sources.id"), nullable=False), op.Column("raw_ingestion_id", ForeignKey("raw_ingestions.id")), op.Column("trading_date", Date, nullable=False), op.Column("close", Numeric(24, 8), nullable=False), op.Column("volume", Numeric(30, 4)), UniqueConstraint("instrument_id", "trading_date", "source_id"))
    op.create_table("estimate_snapshots", op.Column("id", BigInteger, primary_key=True), op.Column("instrument_id", ForeignKey("instruments.id"), nullable=False), op.Column("source_id", ForeignKey("data_sources.id"), nullable=False), op.Column("raw_ingestion_id", ForeignKey("raw_ingestions.id")), op.Column("metric", String(64), nullable=False), op.Column("fiscal_period_label", String(32), nullable=False), op.Column("value", Numeric(30, 8), nullable=False), op.Column("unit", String(32), nullable=False), op.Column("observed_at", DateTime(timezone=True), nullable=False), UniqueConstraint("instrument_id", "source_id", "metric", "fiscal_period_label", "observed_at"))
    op.create_table("changes", op.Column("id", BigInteger, primary_key=True), op.Column("instrument_id", ForeignKey("instruments.id"), nullable=False), op.Column("category", String(32), nullable=False), op.Column("metric", String(64), nullable=False), op.Column("period", String(32)), op.Column("baseline_type", String(32), nullable=False), op.Column("previous_value", Numeric(30, 8)), op.Column("current_value", Numeric(30, 8)), op.Column("absolute_change", Numeric(30, 8)), op.Column("percentage_change", Float), op.Column("direction", String(16), nullable=False), op.Column("change_type", String(32), nullable=False), op.Column("magnitude_score", Float, nullable=False), op.Column("rarity_score", Float, nullable=False), op.Column("relevance_score", Float, nullable=False), op.Column("freshness_score", Float, nullable=False), op.Column("source_quality_score", Float, nullable=False), op.Column("total_score", Float, nullable=False), op.Column("severity", String(16), nullable=False), op.Column("source_id", ForeignKey("data_sources.id")), op.Column("previous_snapshot_id", BigInteger), op.Column("current_snapshot_id", BigInteger), op.Column("detected_at", DateTime(timezone=True), nullable=False), op.Column("metadata", JSON, nullable=False))

def downgrade() -> None:
    for table in ("changes", "events", "flow_daily", "fundamentals", "estimate_snapshots", "price_daily", "job_runs", "raw_ingestions", "watchlist_items", "watchlists", "instrument_aliases", "instruments", "data_sources"):
        op.drop_table(table)
