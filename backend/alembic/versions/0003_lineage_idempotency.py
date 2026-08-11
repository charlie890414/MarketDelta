"""Add snapshot lineage and logical uniqueness constraints."""

import sqlalchemy as sa

from alembic import op

revision = "0003_lineage_idempotency"
down_revision = "0002_domain_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ("flow_daily", "fundamentals"):
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "raw_ingestion_id" not in columns:
            op.add_column(table, sa.Column("raw_ingestion_id", sa.BigInteger(), nullable=True))
            op.create_foreign_key(
                f"fk_{table}_raw_ingestion_id",
                table,
                "raw_ingestions",
                ["raw_ingestion_id"],
                ["id"],
            )
    op.add_column("changes", sa.Column("previous_snapshot_type", sa.String(64)))
    op.add_column("changes", sa.Column("current_snapshot_type", sa.String(64)))
    op.execute(
        """
        UPDATE changes
        SET previous_snapshot_type = CASE category
            WHEN 'price' THEN 'price_daily'
            WHEN 'expectation' THEN 'estimate_snapshots'
            WHEN 'fundamental' THEN 'fundamentals'
            WHEN 'flow' THEN 'flow_daily'
            ELSE NULL
        END,
        current_snapshot_type = CASE category
            WHEN 'price' THEN 'price_daily'
            WHEN 'expectation' THEN 'estimate_snapshots'
            WHEN 'fundamental' THEN 'fundamentals'
            WHEN 'flow' THEN 'flow_daily'
            ELSE NULL
        END
        WHERE previous_snapshot_type IS NULL OR current_snapshot_type IS NULL
        """
    )
    op.create_unique_constraint(
        "uq_flow_daily_logical",
        "flow_daily",
        ["instrument_id", "source_id", "trading_date", "flow_type"],
    )
    op.create_unique_constraint(
        "uq_fundamentals_logical",
        "fundamentals",
        ["instrument_id", "source_id", "metric", "period_label", "observed_at"],
    )
    op.create_index(
        "idx_flow_daily_lookup",
        "flow_daily",
        ["instrument_id", "flow_type", sa.text("trading_date DESC")],
    )
    op.create_index(
        "idx_fundamentals_lookup",
        "fundamentals",
        ["instrument_id", "metric", sa.text("observed_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_fundamentals_lookup", table_name="fundamentals")
    op.drop_index("idx_flow_daily_lookup", table_name="flow_daily")
    op.drop_constraint("uq_fundamentals_logical", "fundamentals", type_="unique")
    op.drop_constraint("uq_flow_daily_logical", "flow_daily", type_="unique")
    op.drop_column("changes", "current_snapshot_type")
    op.drop_column("changes", "previous_snapshot_type")
