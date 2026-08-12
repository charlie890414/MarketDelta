"""Add event lineage and documented metadata fields."""

import sqlalchemy as sa

from alembic import op

revision = "0007_event_lineage_fields"
down_revision = "0006_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("events")}
    additions = {
        "raw_ingestion_id": sa.Column(
            "raw_ingestion_id", sa.BigInteger(), sa.ForeignKey("raw_ingestions.id")
        ),
        "description": sa.Column("description", sa.Text()),
        "starts_at": sa.Column("starts_at", sa.DateTime(timezone=True)),
        "ends_at": sa.Column("ends_at", sa.DateTime(timezone=True)),
        "importance": sa.Column("importance", sa.String(16)),
        "external_id": sa.Column("external_id", sa.String(255)),
        "metadata": sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        "created_at": sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        "updated_at": sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("events", column)


def downgrade() -> None:
    for name in (
        "updated_at",
        "created_at",
        "metadata",
        "external_id",
        "importance",
        "ends_at",
        "starts_at",
        "description",
        "raw_ingestion_id",
    ):
        op.drop_column("events", name)
