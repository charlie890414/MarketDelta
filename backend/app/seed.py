from sqlalchemy import select

from app.data_sources import SOURCE_CATALOG
from app.db.models import DataSource, Watchlist
from app.db.session import SessionLocal


def seed() -> None:
    with SessionLocal() as db:
        for definition in SOURCE_CATALOG:
            source = db.scalar(select(DataSource).where(DataSource.code == definition["code"]))
            metadata = {
                key: definition[key] for key in ("markets", "domains", "cadence", "access", "url")
            }
            if source is None:
                db.add(
                    DataSource(
                        code=definition["code"],
                        name=definition["name"],
                        source_type=definition["source_type"],
                        confidence=definition["confidence"],
                        is_enabled=definition["enabled_by_default"],
                        metadata_=metadata,
                    )
                )
            else:
                source.name = definition["name"]
                source.source_type = definition["source_type"]
                source.confidence = definition["confidence"]
                source.metadata_ = metadata
        db.flush()
        for name in ("Portfolio", "Watchlist", "Research"):
            if not db.scalar(select(Watchlist).where(Watchlist.name == name)):
                db.add(Watchlist(name=name))
        db.commit()


if __name__ == "__main__":
    seed()
