from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PriceObservation(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    trading_date: date
    close: Decimal
    volume: Decimal | None = None
    source_code: str | None = None


class EstimateObservation(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    metric: str
    fiscal_period: str
    value: Decimal
    observed_at: datetime
    unit: str = "USD"


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
    source_code: str | None = None


class OwnershipObservation(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    snapshot_date: date
    holder_bucket: str
    holder_count: int | None = None
    share_count: Decimal | None = None
    ownership_pct: Decimal | None = None


class NewsObservation(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str | None
    external_id: str | None
    headline: str
    published_at: datetime
    source_name: str | None
    source_url: str
    category: str | None = None
    importance_score: float | None = None
    is_material: bool | None = None
    summary: str | None = None


class MacroObservation(BaseModel):
    """One dated observation from a macroeconomic time series."""

    model_config = ConfigDict(frozen=True)
    series_id: str
    observation_date: date
    value: Decimal
    unit: str = "value"
    observed_at: datetime


class ConstituentObservation(BaseModel):
    model_config = ConfigDict(frozen=True)
    fund_symbol: str
    symbol: str
    as_of_date: date
    weight: Decimal | None = None
    source_url: str


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
