"""Add indexes for the high-volume API read paths."""

from alembic import op

revision = "0008_read_path_indexes"
down_revision = "0007_event_lineage_fields"
branch_labels = None
depends_on = None


INDEXES = (
    ("ix_price_daily_instrument_trading_date", "price_daily", ["instrument_id", "trading_date"]),
    ("ix_flow_daily_instrument_trading_date", "flow_daily", ["instrument_id", "trading_date"]),
    (
        "ix_ownership_snapshots_instrument_snapshot_date",
        "ownership_snapshots",
        ["instrument_id", "snapshot_date"],
    ),
    ("ix_estimate_snapshots_instrument_observed_at", "estimate_snapshots", ["instrument_id", "observed_at"]),
    ("ix_fundamentals_instrument_observed_at", "fundamentals", ["instrument_id", "observed_at"]),
    ("ix_events_instrument_event_date", "events", ["instrument_id", "event_date"]),
    ("ix_events_event_date_title", "events", ["event_date", "title"]),
    ("ix_news_items_published_at", "news_items", ["published_at"]),
    ("ix_news_instruments_instrument_news", "news_instruments", ["instrument_id", "news_item_id"]),
    ("ix_changes_instrument_detected_at", "changes", ["instrument_id", "detected_at"]),
    ("ix_ai_interpretations_instrument_generated_at", "ai_interpretations", ["instrument_id", "generated_at"]),
    ("ix_alert_deliveries_delivered_at", "alert_deliveries", ["delivered_at"]),
)


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
