from functools import lru_cache

import httpx

TWSE_COMPANY_DIRECTORY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
SEC_COMPANY_DIRECTORY_URL = "https://www.sec.gov/files/company_tickers.json"


@lru_cache(maxsize=1)
def _twse_companies() -> dict[str, tuple[str, str]]:
    """Return the official TWSE company directory keyed by stock symbol."""
    response = httpx.get(TWSE_COMPANY_DIRECTORY_URL, timeout=10)
    response.raise_for_status()
    return {
        row["公司代號"].strip(): (row["公司名稱"].strip(), "TWSE")
        for row in response.json()
        if row.get("公司代號") and row.get("公司名稱")
    }


def lookup_twse_company(symbol: str) -> tuple[str, str] | None:
    try:
        return _twse_companies().get(symbol)
    except (httpx.HTTPError, TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def _sec_companies(user_agent: str) -> dict[str, str]:
    """Return SEC registrants keyed by their US ticker symbol."""
    response = httpx.get(SEC_COMPANY_DIRECTORY_URL, headers={"User-Agent": user_agent}, timeout=10)
    response.raise_for_status()
    return {
        row["ticker"].upper(): row["title"].strip()
        for row in response.json().values()
        if row.get("ticker") and row.get("title")
    }


def lookup_sec_company(symbol: str, user_agent: str) -> str | None:
    try:
        return _sec_companies(user_agent).get(symbol)
    except (httpx.HTTPError, TypeError, ValueError):
        return None
