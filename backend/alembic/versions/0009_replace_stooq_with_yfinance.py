"""Replace the Stooq data source with Yahoo Finance."""

from alembic import op
import sqlalchemy as sa


revision = "0009_replace_stooq_with_yfinance"
down_revision = "0008_read_path_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    yfinance_id = connection.execute(
        sa.text("SELECT id FROM data_sources WHERE code = 'yfinance'")
    ).scalar()
    if yfinance_id is None:
        yfinance_id = connection.execute(
            sa.text(
                """
                INSERT INTO data_sources (code, name, source_type, confidence, metadata)
                VALUES ('yfinance', 'Yahoo Finance', 'provider', 'medium', '{}')
                RETURNING id
                """
            )
        ).scalar_one()

    stooq_id = connection.execute(
        sa.text("SELECT id FROM data_sources WHERE code = 'stooq'")
    ).scalar()
    if stooq_id is not None:
        for table in ("price_daily", "raw_ingestions", "changes"):
            connection.execute(
                sa.text(f"UPDATE {table} SET source_id = :yfinance_id WHERE source_id = :stooq_id"),
                {"yfinance_id": yfinance_id, "stooq_id": stooq_id},
            )
        connection.execute(sa.text("DELETE FROM data_sources WHERE id = :stooq_id"), {"stooq_id": stooq_id})


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM data_sources WHERE code = 'stooq'")).scalar() is None:
        connection.execute(
            sa.text(
                """
                INSERT INTO data_sources (code, name, source_type, confidence, metadata)
                VALUES ('stooq', 'Stooq', 'provider', 'medium', '{}')
                """
            )
        )
