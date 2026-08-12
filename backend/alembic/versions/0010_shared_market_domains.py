"""Persist macro observations, corporate actions, and exchange calendars."""

import sqlalchemy as sa

from alembic import op

revision = "0010_shared_market_domains"
down_revision = "0009_replace_stooq_with_yfinance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "macro_snapshots",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_id", sa.BigInteger, sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("series_id", sa.String(64), nullable=False),
        sa.Column("observation_date", sa.Date, nullable=False),
        sa.Column("value", sa.Numeric(30, 8), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "series_id", "observation_date"),
    )
    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("instrument_id", sa.BigInteger, sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("source_id", sa.BigInteger, sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("ex_date", sa.Date), sa.Column("pay_date", sa.Date),
        sa.Column("cash_amount", sa.Numeric(30, 8)), sa.Column("ratio", sa.Numeric(30, 8)),
        sa.Column("external_id", sa.String(255)), sa.Column("source_url", sa.Text),
        sa.UniqueConstraint("instrument_id", "source_id", "action_type", "ex_date", "external_id"),
    )
    op.create_table(
        "trading_sessions",
        sa.Column("id", sa.BigInteger, primary_key=True), sa.Column("market", sa.String(16), nullable=False),
        sa.Column("session_date", sa.Date, nullable=False), sa.Column("is_trading_day", sa.Boolean, nullable=False),
        sa.Column("open_at", sa.DateTime(timezone=True)), sa.Column("close_at", sa.DateTime(timezone=True)),
        sa.Column("source_id", sa.BigInteger, sa.ForeignKey("data_sources.id")),
        sa.UniqueConstraint("market", "session_date"),
    )


def downgrade() -> None:
    op.drop_table("trading_sessions")
    op.drop_table("corporate_actions")
    op.drop_table("macro_snapshots")
