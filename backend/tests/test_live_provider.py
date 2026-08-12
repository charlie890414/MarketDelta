from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
import pytest

from app.providers.live import LiveProvider, _latest_closed_us_trading_date


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
