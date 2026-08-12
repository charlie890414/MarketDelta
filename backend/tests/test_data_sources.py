from app.data_sources import SOURCE_CATALOG


def test_source_catalog_covers_required_free_provider_markets_and_domains():
    covered = {
        (market, domain)
        for source in SOURCE_CATALOG
        for market in source["markets"]
        for domain in source["domains"]
    }

    assert {
        ("TW", "prices"),
        ("TW", "fundamentals"),
        ("TW", "flows"),
        ("TW", "ownership"),
        ("US", "prices"),
        ("US", "fundamentals"),
        ("US", "estimates"),
        ("US", "events"),
        ("US", "macro"),
        ("US", "news"),
    } <= covered


def test_catalog_codes_are_unique_and_all_sources_have_provenance():
    assert len({source["code"] for source in SOURCE_CATALOG}) == len(SOURCE_CATALOG)
    assert all(source["url"].startswith("https://") for source in SOURCE_CATALOG)
