from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PriceObservation(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    trading_date: date
    close: Decimal
    volume: Decimal | None = None


class EstimateObservation(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    metric: str
    fiscal_period: str
    value: Decimal
    observed_at: datetime


class FundamentalObservation(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    metric: str
    period: str
    value: Decimal
    unit: str
    observed_at: datetime


class FlowObservation(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    trading_date: date
    flow_type: str
    net_volume: Decimal


class EventObservation(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str | None
    event_type: str
    title: str
    event_date: date | None
    source_url: str | None = None


class ChangeCandidate(BaseModel):
    symbol: str
    market: str
    category: str
    metric: str
    period: str | None
    previous: Decimal | None
    current: Decimal | None
    absolute_change: Decimal | None
    percentage_change: float | None
    direction: str
    change_type: str
    baseline_type: str
