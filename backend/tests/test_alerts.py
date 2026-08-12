from types import SimpleNamespace

import httpx
import pytest

from app.alerts import service


class _Response:
    def raise_for_status(self):
        return None


class _Client:
    attempts = 0
    failures = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json):
        type(self).attempts += 1
        if type(self).attempts <= type(self).failures:
            raise httpx.ConnectError("temporary failure")
        return _Response()


@pytest.mark.asyncio
async def test_dispatch_alerts_retries_then_marks_sent(monkeypatch):
    _Client.attempts = 0
    _Client.failures = 2
    monkeypatch.setattr(service.httpx, "AsyncClient", _Client)
    delivery = SimpleNamespace(id=1, alert_id=2, change_id=3, status="pending")

    await service.dispatch_alerts([delivery], "https://example.invalid", retries=3, backoff_seconds=0)

    assert _Client.attempts == 3
    assert delivery.status == "sent"


@pytest.mark.asyncio
async def test_dispatch_alerts_marks_failed_after_retries(monkeypatch):
    _Client.attempts = 0
    _Client.failures = 5
    monkeypatch.setattr(service.httpx, "AsyncClient", _Client)
    delivery = SimpleNamespace(id=1, alert_id=2, change_id=3, status="pending")

    await service.dispatch_alerts([delivery], "https://example.invalid", retries=2, backoff_seconds=0)

    assert _Client.attempts == 2
    assert delivery.status == "failed"
