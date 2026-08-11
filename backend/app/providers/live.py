from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha1

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
        # Event sources have provider-specific calendars; return no guessed events.
        return []

    async def ownership(self, symbols: Sequence[str]) -> list[OwnershipObservation]:
        return []

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
        return results


def _number(value: object) -> Decimal | None:
    if value is None or value in ("", "-", "None"):
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _first(row: dict, *keys: str) -> object:
    for key in keys:
        if row.get(key) not in (None, "", "-"):
            return row[key]
    return None


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
