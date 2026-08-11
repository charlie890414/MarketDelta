import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.domain.observations import (
    EstimateObservation,
    EventObservation,
    FlowObservation,
    FundamentalObservation,
    PriceObservation,
)

FIXTURES = Path(__file__).parents[2] / "tests" / "fixtures"


class FixtureProvider:
    name = "fixture"

    async def prices(self, symbols: list[str]) -> list[PriceObservation]:
        data = json.loads((FIXTURES / "twse" / "prices.json").read_text())
        return [PriceObservation(**row) for row in data if row["symbol"] in symbols]

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
