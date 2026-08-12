from types import SimpleNamespace

from app.api import routes
from app.db.models import Instrument


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.added = None

    def scalars(self, _statement):
        return self.rows

    def add(self, instrument):
        self.added = instrument

    def commit(self):
        return None

    def refresh(self, _instrument):
        return None


def test_symbol_search_is_not_hidden_by_a_fuzzy_company_name_match(monkeypatch):
    db = FakeSession([Instrument(symbol="GOOG", company_name="Alphabet Inc.")])
    monkeypatch.setattr(routes, "lookup_sec_company", lambda *_args: "Bloom Energy Corporation")
    monkeypatch.setattr(
        routes, "get_settings", lambda: SimpleNamespace(sec_user_agent="test-agent")
    )

    results = routes.search_companies(q="BE", limit=20, db=db)

    assert [instrument.symbol for instrument in results] == ["BE", "GOOG"]
    assert db.added is results[0]
    assert db.added.company_name == "Bloom Energy Corporation"
