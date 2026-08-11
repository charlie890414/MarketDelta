"""Add change lookbacks and persisted daily reports."""

import sqlalchemy as sa

from alembic import op

revision = "0004_reports_and_lookback"
down_revision = "0003_lineage_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    change_columns = {column["name"] for column in inspector.get_columns("changes")}
    if "lookback" not in change_columns:
        op.add_column("changes", sa.Column("lookback", sa.String(32), nullable=True))

    if "daily_reports" not in inspector.get_table_names():
        op.create_table(
            "daily_reports",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("report_date", sa.Date(), nullable=False),
            sa.Column("report_type", sa.String(32), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("report_date", "report_type", name="uq_daily_reports_date_type"),
        )
        op.create_index(
            "idx_daily_reports_date",
            "daily_reports",
            ["report_date", sa.text("created_at DESC")],
        )


def downgrade() -> None:
    op.drop_index("idx_daily_reports_date", table_name="daily_reports")
    op.drop_table("daily_reports")
    op.drop_column("changes", "lookback")
