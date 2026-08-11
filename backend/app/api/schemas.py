from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    company_name: str
    market: str
    category: str
    metric: str
    period: str | None
    previous_value: Decimal | None
    current_value: Decimal | None
    absolute_change: Decimal | None
    percentage_change: float | None
    direction: str
    severity: str
    total_score: float
    source_code: str | None
    source_name: str | None
    source_confidence: str | None
    previous_snapshot_type: str | None
    current_snapshot_type: str | None
    detected_at: datetime


class InstrumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    market: str
    exchange: str | None
    company_name: str
    currency: str


class WatchlistCreate(BaseModel):
    name: str
    description: str | None = None


class WatchlistResponse(WatchlistCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class WatchlistItemCreate(BaseModel):
    symbol: str
    priority: int = 0


class WatchlistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    watchlist_id: int
    instrument_id: int
    symbol: str
    company_name: str
    market: str
    priority: int


class HistoryPoint(BaseModel):
    metric: str
    observed_at: datetime
    value: Decimal
    unit: str


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str | None
    event_type: str
    title: str
    event_date: date | None
    source_url: str | None
    status: str


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    items_fetched: int
    items_inserted: int
    items_changed: int
    items_failed: int
