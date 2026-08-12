from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    company_name: str
    market: str
    category: str
    metric: str
    period: str | None
    lookback: str | None
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
    headline: str | None = None
    event_title: str | None = None
    effective_at: datetime | None = None
    detected_at: datetime


class InstrumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    market: str
    exchange: str | None
    company_name: str
    currency: str


class InstrumentCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    market: Literal["TW", "US"]
    exchange: str | None = Field(default=None, max_length=32)
    company_name: str | None = Field(default=None, max_length=255)


class DataSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    source_type: str
    confidence: str
    is_enabled: bool
    markets: list[str]
    domains: list[str]
    cadence: str | None = None
    access: str | None = None
    url: str | None = None


class WatchlistCreate(BaseModel):
    name: str
    description: str | None = None


class WatchlistUpdate(BaseModel):
    name: str | None = None
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


class NewsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    headline: str
    published_at: datetime
    source_name: str | None
    source_url: str
    category: str | None
    importance_score: float | None
    is_material: bool | None
    summary: str | None
    article_excerpt: str | None = None
    content_status: str
    cluster_key: str | None = None
    ai_confidence: str | None = None


class OwnershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    snapshot_date: date
    holder_bucket: str
    holder_count: int | None
    share_count: Decimal | None
    ownership_pct: Decimal | None


class AIInterpretationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    interpretation_type: str
    summary: str
    why_it_matters: str | None
    supporting_signals: list
    contradictions: list
    watch_next: list
    thesis_impact: str | None
    evidence: list
    confidence: str | None
    data_gaps: list
    model_provider: str
    model_name: str
    prompt_version: str
    generated_at: datetime


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
    error_summary: str | None


class DailyReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    report_date: date
    report_type: str
    title: str
    payload: dict
    created_at: datetime


class InvestmentThesisUpsert(BaseModel):
    thesis: str = Field(min_length=1, max_length=10000)
    key_kpis: list[str] = Field(default_factory=list, max_length=20)
    catalysts: list[str] = Field(default_factory=list, max_length=20)
    risks: list[str] = Field(default_factory=list, max_length=20)
    invalidation_conditions: list[str] = Field(default_factory=list, max_length=20)


class InvestmentThesisResponse(InvestmentThesisUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    created_at: datetime
    updated_at: datetime
