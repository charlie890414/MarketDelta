from app.news.service import _article_text, _news_labels


def test_article_text_prefers_article_and_removes_navigation_noise():
    html = """
    <html><body><nav>navigation noise</nav><article><h1>Headline</h1>
    <p>This is a sufficiently detailed article body with material context. </p>
    <p>It contains more than one hundred and twenty characters so the extractor can
    distinguish an article from a publisher shell, advertisement, or cookie notice.</p></article></body></html>
    """
    content = _article_text(html, 1000)
    assert content is not None
    assert "navigation noise" not in content
    assert "sufficiently detailed article body" in content


def test_news_labels_use_article_text_without_predicting_market_outcome():
    category, score, material, confidence, method = _news_labels(
        "Company updates outlook", "Management raised full-year guidance after earnings."
    )
    assert (category, score, material, confidence, method) == (
        "guidance", 85.0, True, "high", "keyword"
    )
