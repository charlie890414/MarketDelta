"""Add domain tables omitted by older local databases."""
import sqlalchemy as sa

from alembic import op

revision = "0002_domain_tables"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "fundamentals" not in inspector.get_table_names():
        op.create_table("fundamentals", sa.Column("id", sa.BigInteger, primary_key=True), sa.Column("instrument_id", sa.BigInteger, sa.ForeignKey("instruments.id"), nullable=False), sa.Column("source_id", sa.BigInteger, sa.ForeignKey("data_sources.id"), nullable=False), sa.Column("metric", sa.String(64), nullable=False), sa.Column("period_label", sa.String(32), nullable=False), sa.Column("value", sa.Numeric(30, 8), nullable=False), sa.Column("unit", sa.String(32), nullable=False), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False))
    if "flow_daily" not in inspector.get_table_names():
        op.create_table("flow_daily", sa.Column("id", sa.BigInteger, primary_key=True), sa.Column("instrument_id", sa.BigInteger, sa.ForeignKey("instruments.id"), nullable=False), sa.Column("source_id", sa.BigInteger, sa.ForeignKey("data_sources.id"), nullable=False), sa.Column("trading_date", sa.Date, nullable=False), sa.Column("flow_type", sa.String(32), nullable=False), sa.Column("net_volume", sa.Numeric(30, 4), nullable=False), sa.Column("unit", sa.String(16), nullable=False))
    if "events" not in inspector.get_table_names():
        op.create_table("events", sa.Column("id", sa.BigInteger, primary_key=True), sa.Column("instrument_id", sa.BigInteger, sa.ForeignKey("instruments.id")), sa.Column("source_id", sa.BigInteger, sa.ForeignKey("data_sources.id"), nullable=False), sa.Column("event_type", sa.String(64), nullable=False), sa.Column("title", sa.Text, nullable=False), sa.Column("event_date", sa.Date), sa.Column("source_url", sa.Text), sa.Column("status", sa.String(32), nullable=False, server_default="scheduled"))


def downgrade() -> None:
    # These tables are part of 0001 on fresh databases. The compatibility
    # upgrade must never remove them when rolling back this no-op migration.
    pass
