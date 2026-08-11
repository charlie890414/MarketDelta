"""Add configurable score alerts and delivery records."""

import sqlalchemy as sa

from alembic import op

revision = "0006_alerts"
down_revision = "0005_ownership_news_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "alerts" not in tables:
        op.create_table(
            "alerts",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False, unique=True),
            sa.Column("min_score", sa.Float(), nullable=False, server_default="85"),
            sa.Column("category", sa.String(32)),
            sa.Column("market", sa.String(16)),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    if "alert_deliveries" not in tables:
        op.create_table(
            "alert_deliveries",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("alert_id", sa.BigInteger(), sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("change_id", sa.BigInteger(), sa.ForeignKey("changes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("delivered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.UniqueConstraint("alert_id", "change_id", name="uq_alert_delivery_logical"),
        )


def downgrade() -> None:
    op.drop_table("alert_deliveries")
    op.drop_table("alerts")
