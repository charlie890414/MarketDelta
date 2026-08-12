from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pandas as pd
import pytest

from app.providers.live import (
    LiveProvider,
    _latest_closed_us_trading_date,
    _news_queries,
    _sec_filing_events,
)


def test_latest_closed_us_trading_date_excludes_the_in_progress_bar():
    assert _latest_closed_us_trading_date(datetime(2026, 8, 11, 20, 59, tzinfo=UTC)) == date(
        2026, 8, 10
    )
    assert _latest_closed_us_trading_date(datetime(2026, 8, 11, 21, 0, tzinfo=UTC)) == date(
        2026, 8, 11
    )


@pytest.mark.asyncio
async def test_us_price_history_uses_yfinance(monkeypatch):
    requested = {}

    def history(self, **kwargs):
        requested.update(kwargs)
        return pd.DataFrame(
            {"Close": [150.25, 151.5], "Volume": [100, 200]},
            index=pd.to_datetime(["2026-08-10", "2026-08-11"]),
        )

    monkeypatch.setattr("app.providers.live.yf.Ticker.history", history)
    monkeypatch.setattr(
        "app.providers.live._latest_closed_us_trading_date", lambda: date(2026, 8, 10)
    )

    observations = await LiveProvider()._us_price_history("NVDA", date(2026, 8, 10))

    assert [row.trading_date for row in observations] == [date(2026, 8, 10)]
    assert [row.close for row in observations] == [Decimal("150.25")]
    assert requested["end"] == "2026-08-11"
    assert requested["auto_adjust"] is False
    assert requested["actions"] is False


def test_sec_filing_events_keeps_only_material_filing_types_and_builds_edgar_urls():
    events = _sec_filing_events(
        "NVDA",
        {
            "cik": "0001045810",
            "filings": {
                "recent": {
                    "form": ["8-K", "10-Q", "S-8"],
                    "filingDate": ["2026-08-11", "2026-08-01", "2026-07-20"],
                    "accessionNumber": ["0001045810-26-000001", "0001045810-26-000002", "x"],
                    "primaryDocument": ["form8k.htm", "form10q.htm", "form.htm"],
                }
            },
        },
    )

    assert [(event.event_type, event.event_date) for event in events] == [
        ("material_filing", date(2026, 8, 11)),
        ("quarterly_filing", date(2026, 8, 1)),
    ]
    assert events[0].source_code == "sec_filings"
    assert "/1045810/000104581026000001/form8k.htm" in str(events[0].source_url)


@pytest.mark.asyncio
async def test_taiwan_news_uses_taiwan_localized_google_news_query(monkeypatch):
    requested = {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, *, params):
            requested.update(params)
            return httpx.Response(
                200,
                content=(
                    b"<rss><channel><item><title>TSMC</title><link>https://example.com/a</link>"
                    b"<pubDate>Tue, 11 Aug 2026 12:00:00 GMT</pubDate>"
                    b"<source>Example</source></item></channel></rss>"
                ),
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr("app.providers.live.httpx.AsyncClient", lambda **_: Client())
    rows = await LiveProvider().news(
        ["2330"], search_terms={"2330": ["台灣積體電路製造", "台積電"]}
    )

    assert requested["q"] == '"台積電" (股票 OR 營收 OR 法說 OR 股利)'
    assert requested["hl"] == "zh-TW"
    assert requested["gl"] == "TW"
    assert rows[0].symbol == "2330"


def test_news_queries_use_company_names_and_aliases_not_a_bare_ticker():
    taiwan = _news_queries("2330", ["台灣積體電路製造", "台積電"])
    us = _news_queries("AMD", ["Advanced Micro Devices"])

    assert [query for query, _ in taiwan] == [
        '"台灣積體電路製造" (股票 OR 營收 OR 法說 OR 股利)',
        '"台積電" (股票 OR 營收 OR 法說 OR 股利)',
    ]
    assert us[0][0] == '"Advanced Micro Devices" (stock OR earnings OR guidance)'


@pytest.mark.asyncio
async def test_estimates_capture_revenue_and_analyst_count(monkeypatch):
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *_args, **_kwargs):
            return httpx.Response(
                200,
                json={
                    "estimates": [
                        {
                            "fiscalDateEnding": "2026-12-31",
                            "estimatedEPS": "7.25",
                            "estimatedRevenue": "120000000000",
                            "numberOfAnalysts": "42",
                        }
                    ]
                },
                request=httpx.Request("GET", "https://example.com"),
            )

    monkeypatch.setattr("app.providers.live.httpx.AsyncClient", lambda **_: Client())
    monkeypatch.setattr(
        "app.providers.live.get_settings", lambda: type("S", (), {"alpha_vantage_api_key": "key"})()
    )
    rows = await LiveProvider().estimates(["NVDA"])

    assert [(row.metric, row.value, row.unit) for row in rows] == [
        ("eps_estimate", Decimal("7.25"), "USD/share"),
        ("revenue_estimate", Decimal(120000000000), "USD"),
        ("analyst_count", Decimal(42), "analysts"),
    ]
