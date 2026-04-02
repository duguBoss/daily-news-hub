"""Common utility functions for daily news hub."""
from __future__ import annotations

import datetime
import hashlib
import re
import unicodedata
from typing import Any

from daily_news.config import SHANGHAI_TZ


def require_api_key() -> str:
    """Get Gemini API key from environment."""
    import os

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")
    return key


def now_shanghai() -> datetime.datetime:
    """Get current time in Shanghai timezone."""
    return datetime.datetime.now(SHANGHAI_TZ)


def format_date(dt: datetime.datetime | None = None, fmt: str = "%Y-%m-%d") -> str:
    """Format datetime to string."""
    if dt is None:
        dt = now_shanghai()
    return dt.strftime(fmt)


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text[:80]


def is_china_related(text: str) -> bool:
    """Check if text contains China-related keywords."""
    from daily_news.config import CHINA_RELATED_PATTERNS

    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in CHINA_RELATED_PATTERNS)


def sanitize_text(text: str | None) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate_text(text: str, max_chars: int, suffix: str = "...") -> str:
    """Truncate text to max characters."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def count_chinese_chars(text: str) -> int:
    """Count Chinese characters in text."""
    return sum(1 for char in text if "\u4e00" <= char <= "\u9fff")


def compute_hash(text: str) -> str:
    """Compute MD5 hash of text."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:16]


def sanitize_image_url_list(urls: list[str] | None) -> list[str]:
    """Clean and validate image URLs."""
    if not urls:
        return []
    valid_prefixes = ("http://", "https://")
    return [u for u in urls if u and u.startswith(valid_prefixes)]


def normalize_news_item_images(item: dict[str, Any]) -> None:
    """Normalize image fields in news item."""
    if not item.get("image_urls"):
        item["image_urls"] = []
    if not item.get("image_paths"):
        item["image_paths"] = []

    item["image_urls"] = sanitize_image_url_list(item["image_urls"])

    if item["image_urls"] and not item.get("image_url"):
        item["image_url"] = item["image_urls"][0]


def count_news_items_with_images(items: list[dict[str, Any]]) -> int:
    """Count items that have valid images."""
    return sum(1 for item in items if item.get("image_urls"))
