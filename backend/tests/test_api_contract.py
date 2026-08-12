from app.db.base import Base
from app.main import app


def test_documented_domain_routes_are_exposed():
    paths = app.openapi()["paths"]

    expected = {
        "/changes",
        "/data-sources",
        "/companies/search",
        "/companies",
        "/companies/{symbol}/news",
        "/companies/{symbol}/ownership",
        "/companies/{symbol}/interpretations",
        "/companies/{symbol}/interpretations/generate",
        "/companies/{symbol}/thesis",
        "/reports/daily",
        "/reports/daily/ai-generate",
        "/news/{news_id}/enrich",
        "/alerts",
        "/alerts/deliveries",
        "/watchlists/{watchlist_id}",
    }

    assert expected <= paths.keys()


def test_openapi_has_generated_response_contracts():
    schemas = app.openapi()["components"]["schemas"]

    assert {
        "ChangeResponse",
        "DataSourceResponse",
        "DailyReportResponse",
        "NewsResponse",
        "AlertResponse",
        "InvestmentThesisResponse",
    } <= schemas.keys()


def test_high_volume_read_paths_have_composite_indexes():
    expected = {
        "ix_price_daily_instrument_trading_date",
        "ix_flow_daily_instrument_trading_date",
        "ix_ownership_snapshots_instrument_snapshot_date",
        "ix_estimate_snapshots_instrument_observed_at",
        "ix_fundamentals_instrument_observed_at",
        "ix_events_instrument_event_date",
        "ix_news_instruments_instrument_news",
        "ix_changes_instrument_detected_at",
        "ix_ai_interpretations_instrument_generated_at",
    }
    indexes = {index.name for table in Base.metadata.tables.values() for index in table.indexes}

    assert expected <= indexes
