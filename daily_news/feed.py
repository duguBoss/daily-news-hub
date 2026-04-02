"""RSS feed fetching and parsing."""
from __future__ import annotations

from typing import Any

import feedparser
import requests

from daily_news.common import is_china_related, now_shanghai, sanitize_text
from daily_news.config import MAX_NEWS_ITEMS, REQUEST_TIMEOUT, RSS_URL
from daily_news.deduplication import filter_news_items


def fetch_feed() -> Any:
    """Fetch and parse RSS feed."""
    response = requests.get(
        RSS_URL,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "daily-news-hub/1.0"},
    )
    response.raise_for_status()
    return feedparser.parse(response.content)


def resolve_url(url: str) -> str:
    """Resolve URL, following redirects."""
    try:
        resp = requests.head(
            url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}
        )
        return resp.url
    except Exception:
        return url


def collect_news_items(feed: Any, max_articles: int = 5) -> list[dict[str, Any]]:
    """Collect and process news items from feed.
    
    Args:
        feed: Parsed RSS feed
        max_articles: Maximum number of unique articles to return
    """
    raw_items: list[dict[str, Any]] = []

    for idx, entry in enumerate(feed.entries, start=1):
        if len(raw_items) >= MAX_NEWS_ITEMS:
            break

        title = sanitize_text(entry.get("title", ""))
        link = entry.get("link", "")
        summary = sanitize_text(entry.get("summary", ""))

        if not title or not link:
            continue

        resolved = resolve_url(link)

        if is_china_related(f"{title} {resolved}"):
            continue

        item = {
            "index": idx,
            "title": title,
            "google_news_url": link,
            "resolved_url": resolved,
            "summary": summary,
            "image_url": "",
            "image_source": "",
            "image_caption": "",
            "image_path": "",
            "image_urls": [],
            "image_paths": [],
        }
        raw_items.append(item)

    # Deduplicate and limit to max_articles
    return filter_news_items(raw_items, max_articles=max_articles)
