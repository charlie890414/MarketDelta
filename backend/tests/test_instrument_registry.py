from app.instruments import registry


def test_twse_company_lookup_uses_the_official_directory(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"公司代號": "3037", "公司名稱": "欣興電子股份有限公司"}]

    registry._twse_companies.cache_clear()
    monkeypatch.setattr(registry.httpx, "get", lambda *_args, **_kwargs: Response())

    assert registry.lookup_twse_company("3037") == ("欣興電子股份有限公司", "TWSE")
    registry._twse_companies.cache_clear()
