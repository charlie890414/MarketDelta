import csv
import json
from asyncio import to_thread
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from hashlib import sha1
from io import StringIO
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import httpx
import yfinance as yf
from bs4 import BeautifulSoup

from app.config import get_settings
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

US_MARKET_TIMEZONE = ZoneInfo("America/New_York")
US_DAILY_CLOSE_AVAILABLE_AT = time(17)
TDCC_SHAREHOLDING_URL = "https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5"
TPEX_INSTITUTIONAL_FLOW_URL = (
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_3insti_daily_trade"
)
MOPS_MAJOR_INFORMATION_URL = "https://mops.twse.com.tw/mops/web/ajax_t05st01"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


def _latest_closed_us_trading_date(now: datetime | None = None) -> date:
    """Return the latest US date safe to treat as a completed daily bar.

    Yahoo can publish a provisional daily bar during regular trading. We only
    accept the current date after a one-hour post-close buffer (17:00 ET).
    Weekends and holidays are safe: Yahoo returns no bar for non-trading dates.
    """
    market_now = (now or datetime.now(UTC)).astimezone(US_MARKET_TIMEZONE)
    if market_now.weekday() < 5 and market_now.time() >= US_DAILY_CLOSE_AVAILABLE_AT:
        return market_now.date()
    return market_now.date() - timedelta(days=1)


class LiveProvider:
    """Small HTTPX adapter; parsing stays at the provider boundary."""

    name = "live"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def prices(self, symbols: Sequence[str]) -> list[PriceObservation]:
        results: list[PriceObservation] = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            if any(symbol.isdigit() for symbol in symbols):
                response = await client.get(
                    "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
                )
                response.raise_for_status()
                for row in response.json():
                    symbol = str(row.get("Code", ""))
                    if symbol not in symbols:
                        continue
                    close = _number(row.get("ClosingPrice"))
                    if close is None:
                        continue
                    results.append(
                        PriceObservation(
                            symbol=symbol,
                            trading_date=datetime.now(UTC).date(),
                            close=close,
                            volume=_number(row.get("TradeVolume")),
                            source_code="twse",
                        )
                    )
                covered = {observation.symbol for observation in results}
                missing = [
                    symbol for symbol in symbols if symbol.isdigit() and symbol not in covered
                ]
                if missing:
                    response = await client.get(
                        "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close"
                    )
                    response.raise_for_status()
                    for row in response.json():
                        symbol = str(row.get("Code", ""))
                        if symbol not in missing:
                            continue
                        close = _number(row.get("ClosingPrice"))
                        if close is None:
                            continue
                        results.append(
                            PriceObservation(
                                symbol=symbol,
                                trading_date=_tw_date(row.get("Date")) or datetime.now(UTC).date(),
                                close=close,
                                volume=_number(row.get("TradingShares")),
                                source_code="tpex",
                            )
                        )
            # Use yfinance for US daily OHLCV data. Alpha Vantage remains reserved
            # for estimates and earnings events because its request quota is limited.
            covered = {row.symbol for row in results}
            for symbol in symbols:
                if not symbol.isalpha() or symbol in covered:
                    continue
                results.extend(await self._us_prices(symbol))
        return results

    async def price_history(
        self, symbols: Sequence[str], start_date: date
    ) -> list[PriceObservation]:
        """Fetch daily closes for an initial, bounded bootstrap of price history."""
        results: list[PriceObservation] = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for symbol in symbols:
                if symbol.isdigit():
                    results.extend(await self._twse_price_history(client, symbol, start_date))
                elif symbol.isalpha():
                    results.extend(await self._us_price_history(symbol, start_date))
        return results

    async def _us_prices(self, symbol: str) -> list[PriceObservation]:
        return await self._us_price_history(
            symbol, _latest_closed_us_trading_date() - timedelta(days=7)
        )

    async def _us_price_history(self, symbol: str, start_date: date) -> list[PriceObservation]:
        """Retrieve daily OHLCV from yfinance without blocking the async pipeline."""
        try:
            latest_closed_date = _latest_closed_us_trading_date()
            history = await to_thread(
                yf.Ticker(symbol).history,
                start=start_date.isoformat(),
                end=(latest_closed_date + timedelta(days=1)).isoformat(),
                auto_adjust=False,
                actions=False,
            )
            observations = []
            for trading_date, row in history.iterrows():
                close = row.get("Close")
                if close is None or trading_date.date() > latest_closed_date:
                    continue
                observations.append(
                    PriceObservation(
                        symbol=symbol,
                        trading_date=trading_date.date(),
                        close=Decimal(str(close)),
                        volume=_number(row.get("Volume")),
                        source_code="yfinance",
                    )
                )
            return observations
        except Exception:  # noqa: BLE001 - yfinance wraps transport and parsing failures variably.
            return []

    async def _twse_price_history(
        self, client: httpx.AsyncClient, symbol: str, start_date: date
    ) -> list[PriceObservation]:
        observations: dict[date, PriceObservation] = {}
        month = date(start_date.year, start_date.month, 1)
        current_month = datetime.now(UTC).date().replace(day=1)
        while month <= current_month:
            try:
                response = await client.get(
                    "https://www.twse.com.tw/exchangeReport/STOCK_DAY",
                    params={
                        "response": "json",
                        "date": month.strftime("%Y%m%d"),
                        "stockNo": symbol,
                    },
                    headers={"User-Agent": "market-changes-engine/0.1"},
                )
                response.raise_for_status()
                for row in response.json().get("data", []):
                    trading_date = _tw_date(row[0])
                    close = _number(row[6]) if len(row) > 6 else None
                    if trading_date and trading_date >= start_date and close is not None:
                        observations[trading_date] = PriceObservation(
                            symbol=symbol,
                            trading_date=trading_date,
                            close=close,
                            volume=_number(row[1]) if len(row) > 1 else None,
                            source_code="twse",
                        )
            except (httpx.HTTPError, IndexError, TypeError, ValueError):
                pass
            if month.month == 12:
                month = date(month.year + 1, 1, 1)
            else:
                month = date(month.year, month.month + 1, 1)
        return list(observations.values())

    async def estimates(self, symbols: Sequence[str]) -> list[EstimateObservation]:
        if not self.settings.alpha_vantage_api_key:
            return []
        results: list[EstimateObservation] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for symbol in symbols:
                if not symbol.isalpha():
                    continue
                response = await client.get(
                    "https://www.alphavantage.co/query",
                    params={
                        "function": "EARNINGS_ESTIMATES",
                        "symbol": symbol,
                        "apikey": self.settings.alpha_vantage_api_key,
                    },
                )
                response.raise_for_status()
                for row in response.json().get("estimates", []):
                    fiscal_period = row.get("fiscalDateEnding")
                    if not fiscal_period:
                        continue
                    for metric, field, unit in (
                        ("eps_estimate", "estimatedEPS", "USD/share"),
                        ("revenue_estimate", "estimatedRevenue", "USD"),
                        ("analyst_count", "numberOfAnalysts", "analysts"),
                    ):
                        value = _number(row.get(field))
                        if value is None:
                            continue
                        results.append(
                            EstimateObservation(
                                symbol=symbol,
                                metric=metric,
                                fiscal_period=fiscal_period,
                                value=value,
                                observed_at=datetime.now(UTC),
                                unit=unit,
                            )
                        )
        return results

    async def flows(self, symbols: Sequence[str]) -> list[FlowObservation]:
        """Fetch TWSE three-institution net volume from the official JSON feed."""
        results: list[FlowObservation] = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            rows: list[dict] = []
            trading_date = None
            for offset in range(5):
                requested = datetime.now(UTC).date() - timedelta(days=offset)
                response = await client.get(
                    "https://www.twse.com.tw/rwd/zh/fund/T86",
                    params={"date": requested.strftime("%Y%m%d"), "selectType": "ALLBUT0999"},
                    headers={"User-Agent": "market-changes-engine/0.1"},
                )
                response.raise_for_status()
                payload = response.json()
                rows = payload.get("data", [])
                if rows:
                    trading_date = requested
                    break
            if not trading_date:
                return []
            for values in rows:
                row = dict(zip(payload.get("fields", []), values, strict=False))
                symbol = str(_first(row, "證券代號", "Code", "股票代號") or "")
                if symbol not in symbols:
                    continue
                for flow_type, keys in {
                    "foreign_investor": (
                        "外陸資買賣超股數(不含外資自營商)",
                        "ForeignInvestmentNet",
                    ),
                    "investment_trust": ("投信買賣超股數", "InvestmentTrustNet"),
                    "dealer": ("自營商買賣超股數", "DealerNet"),
                }.items():
                    value = _number(_first(row, *keys))
                    if value is not None:
                        results.append(
                            FlowObservation(
                                symbol=symbol,
                                trading_date=trading_date,
                                flow_type=flow_type,
                                net_volume=value,
                            )
                        )
            # TPEx publishes the same three-institution data through its
            # official OpenAPI.  It is a separate market and must not be
            # silently treated as TWSE flow data.
            tpex_response = await client.get(TPEX_INSTITUTIONAL_FLOW_URL)
            tpex_response.raise_for_status()
            results.extend(_parse_tpex_flow_rows(tpex_response.json(), symbols))
        return results

    async def events(self, symbols: Sequence[str]) -> list[EventObservation]:
        results: list[EventObservation] = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            if self.settings.alpha_vantage_api_key:
                response = await client.get(
                    "https://www.alphavantage.co/query",
                    params={
                        "function": "EARNINGS_CALENDAR",
                        "horizon": "3month",
                        "apikey": self.settings.alpha_vantage_api_key,
                    },
                )
                response.raise_for_status()
                for row in csv.DictReader(StringIO(response.text)):
                    symbol = str(row.get("symbol", "")).upper()
                    report_date = str(row.get("reportDate", ""))
                    if symbol not in symbols or not report_date:
                        continue
                    try:
                        event_date = datetime.fromisoformat(report_date).date()
                    except ValueError:
                        continue
                    results.append(
                        EventObservation(
                            symbol=symbol,
                            event_type="earnings",
                            title=f"{row.get('name') or symbol} earnings release",
                            event_date=event_date,
                            source_url="https://www.alphavantage.co/",
                            source_code="alphavantage",
                        )
                    )
            cik_map = await self._sec_cik_map(client, symbols)
            for symbol in symbols:
                cik = cik_map.get(symbol.upper())
                if not cik:
                    continue
                response = await client.get(
                    f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json",
                    headers={"User-Agent": self.settings.sec_user_agent},
                )
                response.raise_for_status()
                results.extend(_sec_filing_events(symbol.upper(), response.json()))
            results.extend(await self._mops_events(client, symbols))
        return results

    async def ownership(self, symbols: Sequence[str]) -> list[OwnershipObservation]:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(TDCC_SHAREHOLDING_URL)
            response.raise_for_status()
            return _parse_tdcc_csv(response.content.decode("utf-8-sig"), symbols)

    async def macro(self) -> list[MacroObservation]:
        """Fetch configured FRED series directly from the official API."""
        if not self.settings.fred_api_key:
            return []
        try:
            series_ids = json.loads(self.settings.fred_series)
        except json.JSONDecodeError:
            return []
        if not isinstance(series_ids, list):
            return []
        results: list[MacroObservation] = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for series_id in series_ids:
                if not isinstance(series_id, str) or not series_id:
                    continue
                response = await client.get(
                    FRED_OBSERVATIONS_URL,
                    params={
                        "series_id": series_id,
                        "api_key": self.settings.fred_api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 2,
                    },
                )
                response.raise_for_status()
                results.extend(_parse_fred_observations(series_id, response.json()))
        return results


    async def news(
        self, symbols: Sequence[str], search_terms: Mapping[str, Sequence[str]] | None = None
    ) -> list[NewsObservation]:
        results: list[NewsObservation] = []
        oldest_allowed = datetime.now(UTC) - timedelta(days=self.settings.news_max_age_days)
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for symbol in symbols:
                seen_urls: set[str] = set()
                for query, locale in _news_queries(symbol, (search_terms or {}).get(symbol, [])):
                    try:
                        response = await client.get(
                            "https://news.google.com/rss/search",
                            params={"q": query, **locale},
                        )
                        response.raise_for_status()
                        items = ElementTree.fromstring(response.content).findall(".//item")
                    except (httpx.HTTPError, ElementTree.ParseError):
                        continue
                    for item in items:
                        headline = (item.findtext("title") or "").strip()
                        url = (item.findtext("link") or "").strip()
                        published = (item.findtext("pubDate") or "").strip()
                        source = item.find("source")
                        if not headline or not url or not published or url in seen_urls:
                            continue
                        try:
                            published_at = parsedate_to_datetime(published).astimezone(UTC)
                        except (TypeError, ValueError):
                            continue
                        if published_at < oldest_allowed:
                            continue
                        seen_urls.add(url)
                        category, importance, material = _classify_news(headline)
                        results.append(
                            NewsObservation(
                                symbol=symbol,
                                external_id=sha1(url.encode(), usedforsecurity=False).hexdigest(),
                                headline=headline,
                                published_at=published_at,
                                source_name=source.text if source is not None else "Google News",
                                source_url=url,
                                category=category,
                                importance_score=importance,
                                is_material=material,
                            )
                        )
        return results

    async def fundamentals(self, symbols: Sequence[str]) -> list[FundamentalObservation]:
        results: list[FundamentalObservation] = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            cik_map = await self._sec_cik_map(client, symbols)
            response = await client.get(
                "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
                headers={"User-Agent": "market-changes-engine/0.1"},
            )
            response.raise_for_status()
            for row in response.json():
                symbol = str(_first(row, "公司代號", "Code") or "")
                period = str(_first(row, "資料年月", "Date") or "")
                value = _number(_first(row, "營業收入-當月營收", "當月營收"))
                if symbol in symbols and period and value is not None:
                    results.append(
                        FundamentalObservation(
                            symbol=symbol,
                            metric="monthly_revenue",
                            period=period,
                            value=value,
                            unit="TWD",
                            observed_at=datetime.now(UTC),
                        )
                    )
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for symbol in symbols:
                cik = cik_map.get(symbol.upper())
                if not cik:
                    continue
                response = await client.get(
                    f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json",
                    headers={"User-Agent": self.settings.sec_user_agent},
                )
                response.raise_for_status()
                facts = response.json().get("facts", {}).get("us-gaap", {})
                tags = {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue_annual",
                    "Revenues": "revenue_annual",
                    "GrossProfit": "gross_profit",
                    "OperatingIncomeLoss": "operating_income",
                    "NetIncomeLoss": "net_income",
                    "CashAndCashEquivalentsAtCarryingValue": "cash",
                    "LongTermDebtNoncurrent": "debt",
                    "NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
                    "EarningsPerShareDiluted": "eps_diluted",
                    "EarningsPerShareBasic": "eps_basic",
                }
                for tag, metric in tags.items():
                    fact_set = facts.get(tag, {}).get("units", {})
                    unit, units = next(iter(fact_set.items()), (None, []))
                    for fact in units:
                        fiscal_period = fact.get("fp")
                        if fiscal_period not in {"FY", "Q1", "Q2", "Q3"}:
                            continue
                        if not fact.get("fy") or not fact.get("filed"):
                            continue
                        results.append(
                            FundamentalObservation(
                                symbol=symbol,
                                metric=metric,
                                period=f"{fiscal_period}{fact['fy']}",
                                value=Decimal(str(fact["val"])),
                                unit=unit or "USD",
                                observed_at=datetime.fromisoformat(fact["filed"]).replace(
                                    tzinfo=UTC
                                ),
                            )
                        )
        return results

    async def _sec_cik_map(
        self, client: httpx.AsyncClient, symbols: Sequence[str]
    ) -> dict[str, str]:
        """Merge optional overrides with SEC's official ticker directory.

        The SEC feed remains the source of truth, while an override lets a user
        pin an unusual ticker during a symbol migration or corporate action.
        """
        try:
            configured = json.loads(getattr(self.settings, "sec_cik_map", "{}"))
        except json.JSONDecodeError:
            configured = {}
        mapping = {
            str(ticker).upper(): str(cik)
            for ticker, cik in configured.items()
            if ticker and cik
        }
        missing = {symbol.upper() for symbol in symbols if symbol.isalpha()} - set(mapping)
        if not missing:
            return mapping
        response = await client.get(
            SEC_TICKERS_URL,
            headers={"User-Agent": getattr(self.settings, "sec_user_agent", "market-changes-engine/0.1")},
        )
        response.raise_for_status()
        for row in response.json().values():
            ticker = str(row.get("ticker", "")).upper()
            if ticker in missing and row.get("cik_str") is not None:
                mapping[ticker] = str(row["cik_str"])
        return mapping

    async def _mops_events(
        self, client: httpx.AsyncClient, symbols: Sequence[str]
    ) -> list[EventObservation]:
        """Read recent MOPS material announcements from the official endpoint.

        MOPS serves this report as an HTML table rather than a stable JSON API.
        The parser keeps the raw announcement title and derives event types only
        for calendar-relevant announcements, preserving the official URL.
        """
        today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Taipei")).date()
        results: list[EventObservation] = []
        for symbol in symbols:
            if not symbol.isdigit():
                continue
            response = await client.get(
                MOPS_MAJOR_INFORMATION_URL,
                params={
                    "TYPEK": "all",
                    "co_id": symbol,
                    "year": str(today.year - 1911),
                    "month": f"{today.month:02d}",
                    "b_date": (today - timedelta(days=31)).strftime("%Y%m%d"),
                    "e_date": today.strftime("%Y%m%d"),
                },
            )
            response.raise_for_status()
            results.extend(_parse_mops_major_information(symbol, response.text, today))
        return results


def _number(value: object) -> Decimal | None:
    if value is None or value in ("", "-", "None"):
        return None
    try:
        text = str(value).replace(",", "").replace("%", "").strip()
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _first(row: dict, *keys: str) -> object:
    for key in keys:
        if row.get(key) not in (None, "", "-"):
            return row[key]
    return None


def _int(value: object) -> int | None:
    try:
        return int(str(value).replace(",", "")) if value not in (None, "", "-") else None
    except ValueError:
        return None


def _parse_mops_rows(
    rows: list[dict], symbols: Sequence[str], observed_at: datetime
) -> list[FundamentalObservation]:
    """Normalize MOPS revenue rows from Chinese or deployment-normalized fields."""
    results: list[FundamentalObservation] = []
    for row in rows:
        symbol = str(_first(row, "公司代號", "證券代號", "symbol", "Code") or "")
        period = str(_first(row, "資料年月", "資料日期", "年月", "period", "Date") or "")
        value = _number(
            _first(row, "營業收入-當月營收", "當月營收", "本月營收", "Revenue", "value")
        )
        if symbol not in symbols or not period or value is None:
            continue
        results.append(
            FundamentalObservation(
                symbol=symbol,
                metric=str(_first(row, "metric", "指標") or "monthly_revenue"),
                period=period,
                value=value,
                unit=str(_first(row, "unit", "幣別") or "TWD"),
                observed_at=observed_at,
            )
        )
    return results


def _parse_tdcc_csv(content: str, symbols: Sequence[str]) -> list[OwnershipObservation]:
    """Normalize TDCC's official weekly shareholding-distribution CSV."""
    return _parse_tdcc_rows(list(csv.DictReader(StringIO(content.lstrip("\ufeff")))), symbols)


def _parse_tpex_flow_rows(rows: list[dict], symbols: Sequence[str]) -> list[FlowObservation]:
    """Normalize TPEx OpenAPI three-institution net trading rows."""
    results: list[FlowObservation] = []
    for row in rows:
        symbol = str(_first(row, "Code", "SecuritiesCompanyCode", "證券代號") or "")
        if symbol not in symbols:
            continue
        trading_date = _tw_date(_first(row, "Date", "資料日期", "交易日期"))
        if not trading_date:
            continue
        fields = {
            "foreign_investor": ("ForeignInvestmentNet", "外資及陸資買賣超股數"),
            "investment_trust": ("InvestmentTrustNet", "投信買賣超股數"),
            "dealer": ("DealerNet", "自營商買賣超股數"),
        }
        for flow_type, keys in fields.items():
            value = _number(_first(row, *keys))
            if value is not None:
                results.append(
                    FlowObservation(
                        symbol=symbol,
                        trading_date=trading_date,
                        flow_type=flow_type,
                        net_volume=value,
                    )
                )
    return results


def _parse_fred_observations(series_id: str, payload: dict) -> list[MacroObservation]:
    """Discard FRED missing values and retain the provider's real-time stamp."""
    rows: list[MacroObservation] = []
    for observation in payload.get("observations", []):
        value = _number(observation.get("value"))
        try:
            observation_date = date.fromisoformat(str(observation["date"]))
        except (KeyError, TypeError, ValueError):
            continue
        if value is None:
            continue
        realtime_end = observation.get("realtime_end") or observation["date"]
        try:
            observed_at = datetime.fromisoformat(str(realtime_end)).replace(tzinfo=UTC)
        except ValueError:
            observed_at = datetime.now(UTC)
        rows.append(
            MacroObservation(
                series_id=series_id,
                observation_date=observation_date,
                value=value,
                observed_at=observed_at,
            )
        )
    return rows


def _parse_mops_major_information(
    symbol: str, html: str, fallback_date: date
) -> list[EventObservation]:
    """Extract MOPS material announcements from its table-oriented response."""
    events: list[EventObservation] = []
    for row in BeautifulSoup(html, "html.parser").select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select("th, td")]
        text = " ".join(cells)
        if symbol not in text or len(cells) < 2:
            continue
        event_date = next((parsed for cell in cells if (parsed := _tw_date(cell))), fallback_date)
        title = next((cell for cell in reversed(cells) if len(cell) > 8), text)
        event_type = _mops_event_type(title)
        if not event_type:
            continue
        events.append(
            EventObservation(
                symbol=symbol,
                event_type=event_type,
                title=title,
                event_date=event_date,
                source_url=MOPS_MAJOR_INFORMATION_URL,
                source_code="mops",
            )
        )
    return events


def _mops_event_type(title: str) -> str | None:
    lowered = title.lower()
    if any(token in title for token in ("股利", "除權", "除息", "盈餘分配")):
        return "dividend"
    if any(token in title for token in ("財務報告", "財報", "合併財務", "財務資訊")):
        return "financial_report"
    if any(token in title for token in ("法人說明會", "法說會", "投資人說明會")):
        return "investor_conference"
    if any(token in lowered for token in ("重大訊息", "material")) or "公告" in title:
        return "material_announcement"
    return None


def _classify_news(headline: str) -> tuple[str, float, bool]:
    """Deterministic, auditable first-pass news classification."""
    text = headline.lower()
    rules = (
        ("earnings", ("earnings", "財報", "營收", "eps"), 70.0),
        ("guidance", ("guidance", "展望", "財測", "下修", "上修"), 85.0),
        ("corporate_action", ("dividend", "股利", "除息", "buyback", "回購", "split"), 80.0),
        ("m&a", ("acquisition", "merger", "併購", "收購"), 90.0),
        ("regulation", ("sec", "lawsuit", "regulatory", "法規", "裁罰"), 85.0),
        ("management", ("ceo", "董事長", "執行長", "人事"), 65.0),
    )
    for category, keywords, importance in rules:
        if any(keyword in text for keyword in keywords):
            return category, importance, importance >= 80
    return "other", 35.0, False


def _parse_tdcc_rows(rows: list[dict], symbols: Sequence[str]) -> list[OwnershipObservation]:
    """Normalize TDCC distribution rows from Chinese or deployment-normalized fields."""
    results: list[OwnershipObservation] = []
    for row in rows:
        symbol = str(_first(row, "證券代號", "公司代號", "symbol", "Code") or "")
        snapshot_date = _tw_date(_first(row, "資料日期", "資料日", "snapshot_date", "Date"))
        if symbol not in symbols or not snapshot_date:
            continue
        results.append(
            OwnershipObservation(
                symbol=symbol,
                snapshot_date=snapshot_date,
                holder_bucket=str(
                    _first(row, "持股分級", "持股級距", "holder_bucket", "HolderBucket")
                    or "unknown"
                ),
                holder_count=_int(_first(row, "人數", "持有人數", "holder_count", "HolderCount")),
                share_count=_number(_first(row, "股數", "持有股數", "share_count", "ShareCount")),
                ownership_pct=_number(
                    _first(
                        row,
                        "占集保庫存數比例",
                        "占集保庫存數比例 (%)",
                        "占集保庫存數比例(%)",
                        "占集保庫存數百分比",
                        "ownership_pct",
                        "OwnershipPct",
                    )
                ),
            )
        )
    return results


def _sec_filing_events(symbol: str, payload: dict) -> list[EventObservation]:
    """Normalize material SEC filings from a company's recent submissions feed."""
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    documents = recent.get("primaryDocument", [])
    filing_types = {
        "8-K": "material_filing",
        "10-Q": "quarterly_filing",
        "10-K": "annual_filing",
        "4": "insider_transaction",
        "13F-HR": "institutional_holding",
        "SC 13G": "beneficial_ownership",
        "SC 13D": "beneficial_ownership",
    }
    cik = str(payload.get("cik", "")).lstrip("0")
    events: list[EventObservation] = []
    for form, filing_date, accession, document in zip(
        forms, dates, accessions, documents, strict=False
    ):
        event_type = filing_types.get(str(form))
        if not event_type:
            continue
        try:
            event_date = date.fromisoformat(str(filing_date))
        except ValueError:
            continue
        accession_id = str(accession).replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_id}/{document}"
            if cik and accession_id and document
            else "https://www.sec.gov/edgar/search/"
        )
        events.append(
            EventObservation(
                symbol=symbol,
                event_type=event_type,
                title=f"SEC Form {form} filed",
                event_date=event_date,
                source_url=url,
                source_code="sec_filings",
            )
        )
    return events


def _news_queries(symbol: str, terms: Sequence[str]) -> list[tuple[str, dict[str, str]]]:
    """Build company-first queries; a ticker is only a disambiguator, never the topic."""
    is_taiwan = symbol.isdigit()
    locale = (
        {"hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"}
        if is_taiwan
        else {"hl": "en-US", "gl": "US", "ceid": "US:en"}
    )
    topic = "股票 OR 營收 OR 法說 OR 股利" if is_taiwan else "stock OR earnings OR guidance"
    unique_terms = list(dict.fromkeys(term.strip() for term in terms if term and term.strip()))
    if not unique_terms:
        unique_terms = [symbol]
    return [(f'"{term}" ({topic})', locale) for term in unique_terms]


def _tw_date(value: object):
    if value is None:
        return None
    text = str(value).replace("-", "").replace("/", "")
    try:
        if len(text) == 7 and text.startswith("11"):
            return date(int(text[:3]) + 1911, int(text[3:5]), int(text[5:]))
        if len(text) == 8:
            return date(int(text[:4]), int(text[4:6]), int(text[6:]))
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
