import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from app.domain.observations import (
    EstimateObservation,
    EventObservation,
    FlowObservation,
    FundamentalObservation,
    NewsObservation,
    OwnershipObservation,
    PriceObservation,
)

FIXTURES = Path(__file__).parents[2] / "tests" / "fixtures"


class FixtureProvider:
    name = "fixture"

    async def prices(self, symbols: list[str]) -> list[PriceObservation]:
        data = json.loads((FIXTURES / "twse" / "prices.json").read_text())
        return [PriceObservation(**row) for row in data if row["symbol"] in symbols]

    async def price_history(self, symbols: list[str], start_date: date) -> list[PriceObservation]:
        return [row for row in await self.prices(symbols) if row.trading_date >= start_date]

    async def estimates(self, symbols: list[str]) -> list[EstimateObservation]:
        data = json.loads((FIXTURES / "alphavantage" / "estimates.json").read_text())
        return [
            EstimateObservation(
                symbol=row["symbol"],
                metric=row["metric"],
                fiscal_period=row["fiscal_period"],
                value=Decimal(str(row["value"])),
                observed_at=datetime.fromisoformat(row["observed_at"]),
            )
            for row in data
            if row["symbol"] in symbols
        ]

    async def flows(self, symbols: list[str]) -> list[FlowObservation]:
        data = json.loads((FIXTURES / "twse" / "flows.json").read_text())
        return [FlowObservation(**row) for row in data if row["symbol"] in symbols]

    async def events(self, symbols: list[str]) -> list[EventObservation]:
        data = json.loads((FIXTURES / "twse" / "events.json").read_text())
        return [
            EventObservation(**row)
            for row in data
            if row.get("symbol") in symbols or row.get("symbol") is None
        ]

    async def fundamentals(self, symbols: list[str]) -> list[FundamentalObservation]:
        data = json.loads((FIXTURES / "twse" / "revenue.json").read_text())
        return [
            FundamentalObservation(
                symbol=row["symbol"],
                metric=row["metric"],
                period=row["period"],
                value=Decimal(str(row["value"])),
                unit=row["unit"],
                observed_at=datetime.fromisoformat(row["observed_at"]),
            )
            for row in data
            if row["symbol"] in symbols
        ]

    async def ownership(self, symbols: list[str]) -> list[OwnershipObservation]:
        data = json.loads((FIXTURES / "twse" / "ownership.json").read_text())
        return [
            OwnershipObservation(
                symbol=row["symbol"],
                snapshot_date=row["snapshot_date"],
                holder_bucket=row["holder_bucket"],
                holder_count=row.get("holder_count"),
                share_count=Decimal(str(row["share_count"])) if row.get("share_count") is not None else None,
                ownership_pct=Decimal(str(row["ownership_pct"])) if row.get("ownership_pct") is not None else None,
            )
            for row in data
            if row["symbol"] in symbols
        ]

    async def news(self, symbols: list[str]) -> list[NewsObservation]:
        data = json.loads((FIXTURES / "news.json").read_text())
        return [
            NewsObservation(**row)
            for row in data
            if row.get("symbol") in symbols or row.get("symbol") is None
        ]
