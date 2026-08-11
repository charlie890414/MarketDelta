from decimal import Decimal

from app.changes.comparator import compare
from app.domain.observations import ChangeCandidate
from app.providers.live import _number, _tw_date
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
