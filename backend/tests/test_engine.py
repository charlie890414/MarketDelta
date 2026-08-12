from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.changes.comparator import compare
from app.changes.engine import _rarity
from app.domain.observations import ChangeCandidate
from app.jobs.pipeline import _fetch_domain
from app.providers.fixture import FixtureProvider
from app.providers.live import _number, _parse_mops_rows, _parse_tdcc_rows, _tw_date
from app.scoring.scorer import score_change, severity


def test_compare_percentage_uses_absolute_baseline():
    absolute, pct, direction = compare(Decimal("6.21"), Decimal("6.48"))
    assert absolute == Decimal("0.27")
    assert round(pct, 2) == 4.35
    assert direction == "up"


def test_zero_baseline_is_not_division_error():
    assert compare(Decimal(0), Decimal(2))[1] is None


def test_score_is_bounded_and_severity_is_deterministic():
    candidate = ChangeCandidate(
        symbol="AMD",
        market="US",
        category="expectation",
        metric="eps_estimate",
        period="FY27",
        previous=Decimal("6.21"),
        current=Decimal("6.48"),
        absolute_change=Decimal("0.27"),
        percentage_change=4.35,
        direction="up",
        change_type="changed",
        baseline_type="previous",
    )
    result = score_change(candidate)
    assert 0 <= result["total"] <= 100
    assert severity(result["total"]) in {"noise", "minor", "notable", "important", "critical"}


def test_live_provider_number_parser_handles_market_placeholders():
    assert _number("1,234") == Decimal(1234)
    assert _number("-") is None
    assert _tw_date("20260811").isoformat() == "2026-08-11"
    assert _tw_date("115/08/11").isoformat() == "2026-08-11"


def test_mops_parser_normalizes_official_chinese_revenue_fields():
    rows = [{"公司代號": "2330", "資料年月": "2026-07", "營業收入-當月營收": "323,000,000,000"}]

    observations = _parse_mops_rows(rows, ["2330"], datetime(2026, 8, 10, tzinfo=UTC))

    assert observations[0].metric == "monthly_revenue"
    assert observations[0].value == Decimal(323000000000)


def test_tdcc_parser_normalizes_official_chinese_distribution_fields():
    rows = [{
        "證券代號": "2330",
        "資料日期": "115/08/11",
        "持股分級": "400001以上",
        "人數": "1,234",
        "股數": "4,210,000,000",
        "占集保庫存數比例": "16.20%",
    }]

    observations = _parse_tdcc_rows(rows, ["2330"])

    assert observations[0].snapshot_date.isoformat() == "2026-08-11"
    assert observations[0].holder_count == 1234
    assert observations[0].ownership_pct == Decimal("16.20")


@pytest.mark.asyncio
async def test_fetch_domain_isolates_provider_failure():
    errors: list[str] = []

    async def failed_fetch() -> list[str]:
        raise TimeoutError("provider timed out")

    assert await _fetch_domain("flows", failed_fetch, errors) == []
    assert errors == ["flows: TimeoutError: provider timed out"]


@pytest.mark.asyncio
async def test_fetch_domain_keeps_successful_domain_result():
    errors: list[str] = []

    async def successful_fetch() -> list[str]:
        return ["observation"]

    assert await _fetch_domain("prices", successful_fetch, errors) == ["observation"]
    assert errors == []


def test_rarity_uses_historical_adjacent_moves():
    rows = [SimpleNamespace(value=value) for value in (110, 100, 99, 98)]

    assert _rarity(rows, lambda row: row.value) == 100


@pytest.mark.asyncio
async def test_fixture_provider_loads_ownership_and_news():
    provider = FixtureProvider()

    ownership = await provider.ownership(["2330"])
    news = await provider.news(["AMD"])

    assert ownership[0].holder_bucket == "gte_400_lots"
    assert news[0].external_id == "fixture-amd-20260811-1"
