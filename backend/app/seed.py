from sqlalchemy import select

from app.db.models import DataSource, Watchlist
from app.db.session import SessionLocal

SOURCES = [
    ("twse", "TWSE", "exchange", "official"),
    ("alphavantage", "Alpha Vantage", "provider", "medium"),
    ("google_news", "Google News RSS", "news", "medium"),
    ("mops", "MOPS", "government", "official"),
    ("tdcc", "TDCC", "government", "official"),
    ("sec", "SEC Company Facts", "government", "official"),
    ("yfinance", "Yahoo Finance", "provider", "medium"),
]
def seed() -> None:
    with SessionLocal() as db:
        for code, name, source_type, confidence in SOURCES:
            if not db.scalar(select(DataSource).where(DataSource.code == code)):
                db.add(
                    DataSource(
                        code=code,
                        name=name,
                        source_type=source_type,
                        confidence=confidence,
                        metadata_={},
                    )
                )
        db.flush()
        for name in ("Portfolio", "Watchlist", "Research"):
            if not db.scalar(select(Watchlist).where(Watchlist.name == name)):
                db.add(Watchlist(name=name))
        db.commit()


if __name__ == "__main__":
    seed()
