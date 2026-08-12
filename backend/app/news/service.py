from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha1

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.db.models import NewsItem


@dataclass(frozen=True)
class ArticleContent:
    text: str | None
    method: str
    error: str | None = None


class NewsClassification(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    importance_score: float = Field(ge=0, le=100)
    is_material: bool
    summary: str = Field(min_length=1, max_length=800)
    confidence: str = Field(pattern="^(high|medium|low)$")
    event_key: str | None = Field(default=None, max_length=128)


def _article_text(html: str, max_chars: int) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "aside", "form", "noscript"]):
        node.decompose()
    root = soup.select_one("article") or soup.select_one("main") or soup.body
    if not root:
        return None
    text = re.sub(r"\s+", " ", root.get_text(" ", strip=True)).strip()
    return text[:max_chars] if len(text) >= 120 else None


async def _camoufox_html(url: str, timeout_seconds: float) -> str | None:
    """Use a real browser only after normal HTTP retrieval cannot expose article text."""
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError:
        return None
    try:
        async with AsyncCamoufox(headless=True) as browser:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_seconds * 1000))
            await page.wait_for_timeout(400)
            return await page.content()
    except Exception:  # noqa: BLE001 - browser backends expose implementation-specific errors.
        return None


async def fetch_article_content(url: str) -> ArticleContent:
    settings = get_settings()
    headers = {"User-Agent": "MarketDelta/0.1 research content fetcher"}
    try:
        async with httpx.AsyncClient(
            timeout=settings.news_content_timeout_seconds, follow_redirects=True, headers=headers
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            text = _article_text(response.text, settings.news_content_max_chars)
            if text:
                return ArticleContent(text=text, method="httpx")
    except httpx.HTTPError as exc:
        http_error = type(exc).__name__
    else:
        http_error = "article_text_not_found"
    if settings.news_camoufox_enabled:
        html = await _camoufox_html(url, settings.news_content_timeout_seconds)
        text = _article_text(html or "", settings.news_content_max_chars)
        if text:
            return ArticleContent(text=text, method="camoufox")
    return ArticleContent(text=None, method="failed", error=http_error)


def _news_labels(headline: str, article_text: str | None) -> tuple[str, float, bool, str, str]:
    """Auditable fallback used when an LLM is unavailable; it never infers unobserved facts."""
    text = f"{headline} {article_text or ''}".lower()
    rules = (
        ("m&a", ("acquisition", "merger", "併購", "收購"), 90.0),
        ("guidance", ("guidance", "展望", "財測", "下修", "上修"), 85.0),
        ("regulation", ("sec", "lawsuit", "regulatory", "法規", "裁罰"), 85.0),
        ("corporate_action", ("dividend", "股利", "除息", "buyback", "回購", "split"), 80.0),
        ("earnings", ("earnings", "財報", "營收", "eps"), 70.0),
        ("management", ("ceo", "董事長", "執行長", "人事"), 65.0),
    )
    for category, keywords, score in rules:
        if any(word in text for word in keywords):
            return category, score, score >= 80, "high" if article_text else "medium", "keyword"
    return "other", 35.0, False, "low" if not article_text else "medium", "keyword"


async def _llm_labels(headline: str, article_text: str | None) -> NewsClassification | None:
    settings = get_settings()
    if not settings.llm_base_url or not settings.llm_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Classify this market news from the supplied text only. Do not predict prices, "
                                "recommend trades, or add unstated facts. Return JSON: category, "
                                "importance_score (0-100), is_material, summary, confidence (high|medium|low), "
                                "event_key (a stable short identifier for the same underlying event, or null)."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Headline: {headline}\nArticle: {article_text or 'Unavailable'}",
                        },
                    ],
                },
            )
            response.raise_for_status()
            return NewsClassification.model_validate_json(
                response.json()["choices"][0]["message"]["content"]
            )
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValidationError, ValueError):
        return None


async def enrich_news_item(item: NewsItem) -> None:
    """Fetch article body, classify it, and persist provenance without changing objective signals."""
    content = await fetch_article_content(item.source_url)
    llm = await _llm_labels(item.headline, content.text)
    category, score, material, confidence, classifier = _news_labels(item.headline, content.text)
    item.article_text = content.text
    item.content_status = "fetched" if content.text else "failed"
    item.content_fetched_at = datetime.now(UTC)
    item.category = llm.category if llm else category
    item.importance_score = llm.importance_score if llm else score
    item.is_material = llm.is_material if llm else material
    item.summary = llm.summary if llm else None
    item.ai_confidence = llm.confidence if llm else confidence
    item.cluster_key = (llm.event_key if llm else None) or sha1(
        re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", item.headline.lower()).strip().encode(),
        usedforsecurity=False,
    ).hexdigest()[:20]
    item.metadata_ = {
        **(item.metadata_ or {}),
        "content_method": content.method,
        "content_error": content.error,
        "classification_method": "llm" if llm else classifier,
    }
