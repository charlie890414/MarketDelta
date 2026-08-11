from collections.abc import Sequence
from typing import Protocol

from app.domain.observations import (
    EstimateObservation,
    EventObservation,
    FlowObservation,
    FundamentalObservation,
    PriceObservation,
)


class Provider(Protocol):
    name: str

    async def prices(self, symbols: Sequence[str]) -> list[PriceObservation]: ...
    async def estimates(self, symbols: Sequence[str]) -> list[EstimateObservation]: ...
    async def fundamentals(self, symbols: Sequence[str]) -> list[FundamentalObservation]: ...
    async def flows(self, symbols: Sequence[str]) -> list[FlowObservation]: ...
    async def events(self, symbols: Sequence[str]) -> list[EventObservation]: ...
