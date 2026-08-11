from sqlalchemy import select

from app.db.models import DataSource, Instrument, InstrumentAlias, Watchlist
from app.db.session import SessionLocal

SOURCES = [
    ("twse", "TWSE", "exchange", "official"),
    ("alphavantage", "Alpha Vantage", "provider", "medium"),
]
INSTRUMENTS = [
    ("AMD", "US", "NASDAQ", "Advanced Micro Devices", "USD"),
    ("NVDA", "US", "NASDAQ", "NVIDIA Corporation", "USD"),
    ("TSM", "US", "NYSE", "Taiwan Semiconductor Manufacturing ADR", "USD"),
    ("2330", "TW", "TWSE", "Taiwan Semiconductor Manufacturing", "TWD"),
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
        for symbol, market, exchange, company_name, currency in INSTRUMENTS:
            instrument = db.scalar(
                select(Instrument).where(Instrument.market == market, Instrument.symbol == symbol)
            )
            if not instrument:
                instrument = Instrument(
                    symbol=symbol,
                    market=market,
                    exchange=exchange,
                    company_name=company_name,
                    currency=currency,
                )
                db.add(instrument)
                db.flush()
            if symbol == "TSM" and not db.scalar(
                select(InstrumentAlias).where(InstrumentAlias.alias == "TSMC")
            ):
                db.add(
                    InstrumentAlias(instrument_id=instrument.id, alias="TSMC", alias_type="symbol")
                )
        for name in ("Portfolio", "Watchlist", "Research"):
            if not db.scalar(select(Watchlist).where(Watchlist.name == name)):
                db.add(Watchlist(name=name))
        db.commit()


if __name__ == "__main__":
    seed()
