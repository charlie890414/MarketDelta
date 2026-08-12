from app.main import app


def test_documented_domain_routes_are_exposed():
    paths = app.openapi()["paths"]

    expected = {
        "/changes",
        "/companies/search",
        "/companies/{symbol}/news",
        "/companies/{symbol}/ownership",
        "/companies/{symbol}/interpretations",
        "/companies/{symbol}/interpretations/generate",
        "/reports/daily",
        "/alerts",
        "/alerts/deliveries",
        "/watchlists/{watchlist_id}",
    }

    assert expected <= paths.keys()


def test_openapi_has_generated_response_contracts():
    schemas = app.openapi()["components"]["schemas"]

    assert {"ChangeResponse", "DailyReportResponse", "NewsResponse", "AlertResponse"} <= schemas.keys()
