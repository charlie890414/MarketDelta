"""Add ownership, news, and AI interpretation persistence."""

import sqlalchemy as sa

from alembic import op

revision = "0005_ownership_news_ai"
down_revision = "0004_reports_and_lookback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "ownership_snapshots" not in tables:
        op.create_table(
            "ownership_snapshots",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("instrument_id", sa.BigInteger(), sa.ForeignKey("instruments.id"), nullable=False),
            sa.Column("source_id", sa.BigInteger(), sa.ForeignKey("data_sources.id"), nullable=False),
            sa.Column("raw_ingestion_id", sa.BigInteger(), sa.ForeignKey("raw_ingestions.id")),
            sa.Column("snapshot_date", sa.Date(), nullable=False),
            sa.Column("holder_bucket", sa.String(64), nullable=False),
            sa.Column("holder_count", sa.BigInteger()),
            sa.Column("share_count", sa.Numeric(30, 4)),
            sa.Column("ownership_pct", sa.Numeric(12, 8)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint(
                "instrument_id", "source_id", "snapshot_date", "holder_bucket",
                name="uq_ownership_logical",
            ),
        )
        op.create_index(
            "idx_ownership_snapshots_lookup",
            "ownership_snapshots",
            ["instrument_id", "holder_bucket", sa.text("snapshot_date DESC")],
        )

    if "news_items" not in tables:
        op.create_table(
            "news_items",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("source_id", sa.BigInteger(), sa.ForeignKey("data_sources.id"), nullable=False),
            sa.Column("raw_ingestion_id", sa.BigInteger(), sa.ForeignKey("raw_ingestions.id")),
            sa.Column("external_id", sa.String(255)),
            sa.Column("headline", sa.Text(), nullable=False),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("source_name", sa.String(255)),
            sa.Column("source_url", sa.Text(), nullable=False),
            sa.Column("category", sa.String(64)),
            sa.Column("importance_score", sa.Float()),
            sa.Column("is_material", sa.Boolean()),
            sa.Column("summary", sa.Text()),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("idx_news_items_published", "news_items", [sa.text("published_at DESC")])
        op.create_index(
            "idx_news_items_category_published",
            "news_items",
            ["category", sa.text("published_at DESC")],
        )
        op.create_index(
            "uq_news_items_source_external",
            "news_items",
            ["source_id", "external_id"],
            unique=True,
            postgresql_where=sa.text("external_id IS NOT NULL"),
        )

    if "news_instruments" not in tables:
        op.create_table(
            "news_instruments",
            sa.Column(
                "news_item_id", sa.BigInteger(),
                sa.ForeignKey("news_items.id", ondelete="CASCADE"), primary_key=True,
            ),
            sa.Column(
                "instrument_id", sa.BigInteger(),
                sa.ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True,
            ),
            sa.Column("relevance_score", sa.Float()),
        )

    if "ai_interpretations" not in tables:
        op.create_table(
            "ai_interpretations",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("instrument_id", sa.BigInteger(), sa.ForeignKey("instruments.id"), nullable=False),
            sa.Column("interpretation_type", sa.String(32), nullable=False, server_default="change"),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("why_it_matters", sa.Text()),
            sa.Column("supporting_signals", sa.JSON(), nullable=False),
            sa.Column("contradictions", sa.JSON(), nullable=False),
            sa.Column("watch_next", sa.JSON(), nullable=False),
            sa.Column("thesis_impact", sa.String(32)),
            sa.Column("model_provider", sa.String(64), nullable=False),
            sa.Column("model_name", sa.String(128), nullable=False),
            sa.Column("prompt_version", sa.String(64), nullable=False),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False),
        )

    if "ai_interpretation_changes" not in tables:
        op.create_table(
            "ai_interpretation_changes",
            sa.Column(
                "interpretation_id", sa.BigInteger(),
                sa.ForeignKey("ai_interpretations.id", ondelete="CASCADE"), primary_key=True,
            ),
            sa.Column(
                "change_id", sa.BigInteger(),
                sa.ForeignKey("changes.id", ondelete="CASCADE"), primary_key=True,
            ),
        )


def downgrade() -> None:
    op.drop_table("ai_interpretation_changes")
    op.drop_table("ai_interpretations")
    op.drop_table("news_instruments")
    op.drop_index("uq_news_items_source_external", table_name="news_items")
    op.drop_index("idx_news_items_category_published", table_name="news_items")
    op.drop_index("idx_news_items_published", table_name="news_items")
    op.drop_table("news_items")
    op.drop_index("idx_ownership_snapshots_lookup", table_name="ownership_snapshots")
    op.drop_table("ownership_snapshots")
