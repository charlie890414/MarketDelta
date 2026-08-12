import csv
import json
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha1
from io import StringIO

import httpx

from app.config import get_settings
from app.domain.observations import (
    EstimateObservation,
    EventObservation,
    FlowObservation,
    FundamentalObservation,
    NewsObservation,
    OwnershipObservation,
    PriceObservation,
)


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
                        )
                    )
                covered = {observation.symbol for observation in results}
                missing = [symbol for symbol in symbols if symbol.isdigit() and symbol not in covered]
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
                            )
                        )
            for symbol in symbols:
                if not symbol.isalpha() or not self.settings.alpha_vantage_api_key:
                    continue
                response = await client.get(
                    "https://www.alphavantage.co/query",
                    params={
                        "function": "TIME_SERIES_DAILY",
                        "symbol": symbol,
                        "outputsize": "compact",
                        "apikey": self.settings.alpha_vantage_api_key,
                    },
                )
                response.raise_for_status()
                series = response.json().get("Time Series (Daily)", {})
                if not series:
                    continue
                trading_date = max(series)
                row = series[trading_date]
                results.append(
                    PriceObservation(
                        symbol=symbol,
                        trading_date=datetime.fromisoformat(trading_date).date(),
                        close=Decimal(row["4. close"]),
                        volume=Decimal(row["5. volume"]),
                    )
                )
            # Stooq is a free, keyless fallback for US daily OHLCV data.
            covered = {row.symbol for row in results}
            if self.settings.stooq_enabled:
                for symbol in symbols:
                    if not symbol.isalpha() or symbol in covered:
                        continue
                    try:
                        response = await client.get(
                            "https://stooq.com/q/d/l/",
                            params={"s": f"{symbol.lower()}.us", "i": "d"},
                        )
                        response.raise_for_status()
                        rows = list(csv.DictReader(StringIO(response.text)))
                        if not rows:
                            continue
                        row = rows[-1]
                        results.append(PriceObservation(
                            symbol=symbol,
                            trading_date=date.fromisoformat(row["Date"]),
                            close=Decimal(row["Close"]),
                            volume=_number(row.get("Volume")),
                        ))
                    except (httpx.HTTPError, KeyError, ValueError, InvalidOperation):
                        continue
        return results

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
                    value = _number(row.get("estimatedEPS"))
                    if not fiscal_period or value is None:
                        continue
                    results.append(
                        EstimateObservation(
                            symbol=symbol,
                            metric="eps_estimate",
                            fiscal_period=fiscal_period,
                            value=value,
                            observed_at=datetime.now(UTC),
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
        return results

    async def events(self, symbols: Sequence[str]) -> list[EventObservation]:
        if not self.settings.alpha_vantage_api_key:
            return []
        results: list[EventObservation] = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
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
                    )
                )
        return results

    async def ownership(self, symbols: Sequence[str]) -> list[OwnershipObservation]:
        if not self.settings.tdcc_api_url:
            return []
        results: list[OwnershipObservation] = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(self.settings.tdcc_api_url)
            response.raise_for_status()
            results.extend(_parse_tdcc_rows(response.json(), symbols))
        return results

    async def news(self, symbols: Sequence[str]) -> list[NewsObservation]:
        if not self.settings.alpha_vantage_api_key:
            return []
        results: list[NewsObservation] = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "NEWS_SENTIMENT",
                    "tickers": ",".join(symbols),
                    "limit": 100,
                    "apikey": self.settings.alpha_vantage_api_key,
                },
            )
            response.raise_for_status()
            for item in response.json().get("feed", []):
                headline = str(item.get("title", "")).strip()
                url = str(item.get("url", "")).strip()
                published = str(item.get("time_published", ""))
                if not headline or not url or len(published) < 15:
                    continue
                try:
                    published_at = datetime.strptime(published[:15], "%Y%m%dT%H%M%S").replace(
                        tzinfo=UTC
                    )
                except ValueError:
                    continue
                tickers = {
                    str(entry.get("ticker", "")).upper()
                    for entry in item.get("ticker_sentiment", [])
                }
                matched = next((symbol for symbol in symbols if symbol.upper() in tickers), None)
                sentiment = _number(item.get("overall_sentiment_score"))
                results.append(
                    NewsObservation(
                        symbol=matched,
                        external_id=sha1(url.encode(), usedforsecurity=False).hexdigest(),
                        headline=headline,
                        published_at=published_at,
                        source_name=item.get("source"),
                        source_url=url,
                        category=(item.get("topics") or [{}])[0].get("topic"),
                        importance_score=float(abs(sentiment or 0) * 100),
                        is_material=abs(sentiment or 0) >= Decimal("0.35"),
                        summary=item.get("summary"),
                    )
                )
        return results

    async def fundamentals(self, symbols: Sequence[str]) -> list[FundamentalObservation]:
        results: list[FundamentalObservation] = []
        cik_map = json.loads(self.settings.sec_cik_map)
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
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
                }
                for tag, metric in tags.items():
                    fact_set = facts.get(tag, {}).get("units", {})
                    unit, units = next(iter(fact_set.items()), (None, []))
                    for fact in units:
                        if fact.get("fp") != "FY" or not fact.get("fy") or not fact.get("filed"):
                            continue
                        results.append(FundamentalObservation(
                            symbol=symbol, metric=metric, period=f"FY{fact['fy']}",
                            value=Decimal(str(fact["val"])), unit=unit or "USD",
                            observed_at=datetime.fromisoformat(fact["filed"]).replace(tzinfo=UTC),
                        ))
            if self.settings.mops_api_url:
                response = await client.get(self.settings.mops_api_url)
                response.raise_for_status()
                results.extend(_parse_mops_rows(response.json(), symbols, datetime.now(UTC)))
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


def _parse_tdcc_rows(rows: list[dict], symbols: Sequence[str]) -> list[OwnershipObservation]:
    """Normalize TDCC distribution rows from Chinese or deployment-normalized fields."""
    results: list[OwnershipObservation] = []
    for row in rows:
        symbol = str(_first(row, "證券代號", "公司代號", "symbol", "Code") or "")
        snapshot_date = _tw_date(
            _first(row, "資料日期", "資料日", "snapshot_date", "Date")
        )
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
                        "占集保庫存數百分比",
                        "ownership_pct",
                        "OwnershipPct",
                    )
                ),
            )
        )
    return results


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
