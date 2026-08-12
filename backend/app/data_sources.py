"""Authoritative source inventory and coverage metadata.

The catalog deliberately includes sources that are not yet enabled.  This makes
coverage gaps visible to the API/UI instead of silently treating an unavailable
domain as having no market activity.
"""

from typing import TypedDict


class SourceDefinition(TypedDict):
    code: str
    name: str
    source_type: str
    confidence: str
    markets: list[str]
    domains: list[str]
    cadence: str
    access: str
    enabled_by_default: bool
    url: str


SOURCE_CATALOG: tuple[SourceDefinition, ...] = (
    {
        "code": "twse",
        "name": "Taiwan Stock Exchange",
        "source_type": "exchange",
        "confidence": "official",
        "markets": ["TW"],
        "domains": ["prices", "flows", "instruments"],
        "cadence": "daily",
        "access": "public_api",
        "enabled_by_default": True,
        "url": "https://openapi.twse.com.tw/",
    },
    {
        "code": "tpex",
        "name": "Taipei Exchange",
        "source_type": "exchange",
        "confidence": "official",
        "markets": ["TW"],
        "domains": ["prices", "flows", "instruments"],
        "cadence": "daily",
        "access": "public_api",
        "enabled_by_default": True,
        "url": "https://www.tpex.org.tw/openapi/",
    },
    {
        "code": "mops",
        "name": "Market Observation Post System",
        "source_type": "government",
        "confidence": "official",
        "markets": ["TW"],
        "domains": ["fundamentals", "events", "corporate_actions", "governance"],
        "cadence": "filing",
        "access": "public_html_report",
        "enabled_by_default": True,
        "url": "https://mops.twse.com.tw/",
    },
    {
        "code": "tdcc",
        "name": "Taiwan Depository & Clearing Corporation",
        "source_type": "government",
        "confidence": "official",
        "markets": ["TW"],
        "domains": ["ownership"],
        "cadence": "weekly",
        "access": "public_open_data",
        "enabled_by_default": True,
        "url": "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
    },
    {
        "code": "sec",
        "name": "SEC EDGAR Company Facts",
        "source_type": "government",
        "confidence": "official",
        "markets": ["US"],
        "domains": ["fundamentals", "instruments"],
        "cadence": "filing",
        "access": "public_api",
        "enabled_by_default": True,
        "url": "https://data.sec.gov/api/xbrl/",
    },
    {
        "code": "sec_filings",
        "name": "SEC EDGAR Submissions",
        "source_type": "government",
        "confidence": "official",
        "markets": ["US"],
        "domains": ["events", "ownership", "governance"],
        "cadence": "near_realtime",
        "access": "public_api",
        "enabled_by_default": True,
        "url": "https://data.sec.gov/submissions/",
    },
    {
        "code": "yfinance",
        "name": "Yahoo Finance",
        "source_type": "provider",
        "confidence": "medium",
        "markets": ["US"],
        "domains": ["prices", "corporate_actions"],
        "cadence": "daily",
        "access": "library",
        "enabled_by_default": True,
        "url": "https://finance.yahoo.com/",
    },
    {
        "code": "alphavantage",
        "name": "Alpha Vantage",
        "source_type": "provider",
        "confidence": "medium",
        "markets": ["US"],
        "domains": ["estimates", "events"],
        "cadence": "daily",
        "access": "api_key",
        "enabled_by_default": True,
        "url": "https://www.alphavantage.co/",
    },
    {
        "code": "fred",
        "name": "Federal Reserve Economic Data",
        "source_type": "government",
        "confidence": "official",
        "markets": ["US", "TW"],
        "domains": ["macro"],
        "cadence": "series_dependent",
        "access": "api_key",
        "enabled_by_default": True,
        "url": "https://fred.stlouisfed.org/docs/api/",
    },
    {
        "code": "google_news",
        "name": "Google News RSS",
        "source_type": "news",
        "confidence": "medium",
        "markets": ["US", "TW"],
        "domains": ["news"],
        "cadence": "near_realtime",
        "access": "public_rss",
        "enabled_by_default": True,
        "url": "https://news.google.com/",
    },
)
