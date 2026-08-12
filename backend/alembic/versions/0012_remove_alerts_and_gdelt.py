"""Remove the discontinued alert subsystem and GDELT catalog entry."""

import sqlalchemy as sa

from alembic import op

revision = "0012_remove_alerts_and_gdelt"
down_revision = "0011_ai_research_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("alert_deliveries", if_exists=True)
    op.drop_table("alerts", if_exists=True)
    op.execute(sa.text("DELETE FROM data_sources WHERE code = 'gdelt'"))


def downgrade() -> None:
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
    op.create_table(
        "alert_deliveries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "alert_id", sa.BigInteger(), sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "change_id", sa.BigInteger(), sa.ForeignKey("changes.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.UniqueConstraint("alert_id", "change_id", name="uq_alert_delivery_logical"),
    )
    op.create_index("ix_alert_deliveries_delivered_at", "alert_deliveries", ["delivered_at"])
