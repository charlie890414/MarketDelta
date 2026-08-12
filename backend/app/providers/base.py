from collections.abc import Mapping, Sequence
from datetime import date
from typing import Protocol

from app.domain.observations import (
    EstimateObservation,
    EventObservation,
    FlowObservation,
    FundamentalObservation,
    MacroObservation,
    NewsObservation,
    OwnershipObservation,
    PriceObservation,
)


class Provider(Protocol):
    name: str

    async def prices(self, symbols: Sequence[str]) -> list[PriceObservation]: ...
    async def price_history(
        self, symbols: Sequence[str], start_date: date
    ) -> list[PriceObservation]: ...
    async def estimates(self, symbols: Sequence[str]) -> list[EstimateObservation]: ...
    async def fundamentals(self, symbols: Sequence[str]) -> list[FundamentalObservation]: ...
    async def flows(self, symbols: Sequence[str]) -> list[FlowObservation]: ...
    async def events(self, symbols: Sequence[str]) -> list[EventObservation]: ...
    async def ownership(self, symbols: Sequence[str]) -> list[OwnershipObservation]: ...
    async def macro(self) -> list[MacroObservation]: ...
    async def news(
        self, symbols: Sequence[str], search_terms: Mapping[str, Sequence[str]] | None = None
    ) -> list[NewsObservation]: ...
