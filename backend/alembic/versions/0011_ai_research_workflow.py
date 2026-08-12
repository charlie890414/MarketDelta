"""Add article content, evidence-backed interpretation, and investment theses."""

import sqlalchemy as sa
from alembic import op

revision = "0011_ai_research_workflow"
down_revision = "0010_shared_market_domains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("news_items", sa.Column("article_text", sa.Text()))
    op.add_column("news_items", sa.Column("content_status", sa.String(32), nullable=False, server_default="pending"))
    op.add_column("news_items", sa.Column("content_fetched_at", sa.DateTime(timezone=True)))
    op.add_column("news_items", sa.Column("cluster_key", sa.String(128)))
    op.add_column("news_items", sa.Column("ai_confidence", sa.String(16)))
    op.create_index("ix_news_items_cluster_key", "news_items", ["cluster_key"])
    op.add_column("ai_interpretations", sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("ai_interpretations", sa.Column("confidence", sa.String(16)))
    op.add_column("ai_interpretations", sa.Column("data_gaps", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table(
        "investment_theses",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("instrument_id", sa.BigInteger(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("key_kpis", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("catalysts", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("risks", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("invalidation_conditions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_investment_theses_instrument_updated_at", "investment_theses", ["instrument_id", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_investment_theses_instrument_updated_at", table_name="investment_theses")
    op.drop_table("investment_theses")
    op.drop_column("ai_interpretations", "data_gaps")
    op.drop_column("ai_interpretations", "confidence")
    op.drop_column("ai_interpretations", "evidence")
    op.drop_index("ix_news_items_cluster_key", table_name="news_items")
    op.drop_column("news_items", "ai_confidence")
    op.drop_column("news_items", "cluster_key")
    op.drop_column("news_items", "content_fetched_at")
    op.drop_column("news_items", "content_status")
    op.drop_column("news_items", "article_text")
