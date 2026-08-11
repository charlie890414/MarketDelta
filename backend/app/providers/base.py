from collections.abc import Sequence
from typing import Protocol

from app.domain.observations import EstimateObservation, PriceObservation


class Provider(Protocol):
    name: str

    async def prices(self, symbols: Sequence[str]) -> list[PriceObservation]: ...
    async def estimates(self, symbols: Sequence[str]) -> list[EstimateObservation]: ...
