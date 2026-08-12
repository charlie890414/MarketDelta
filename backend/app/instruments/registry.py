from functools import lru_cache

import httpx

TWSE_COMPANY_DIRECTORY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"


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
