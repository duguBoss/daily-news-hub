"""Data validation functions."""
from __future__ import annotations

from typing import Any

from daily_news.config import MIN_NEWS_ITEMS


def validate_ai_data(ai_data: dict[str, Any], news_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate and fix AI-generated data structure."""
    if not isinstance(ai_data, dict):
        raise ValueError("AI data must be a dictionary")

    required_keys = ["title", "articles", "editorial_notes", "tags"]
    for key in required_keys:
        if key not in ai_data:
            raise ValueError(f"Missing required key: {key}")

    if not isinstance(ai_data["articles"], list) or len(ai_data["articles"]) == 0:
        raise ValueError("Articles must be a non-empty list")

    for i, article in enumerate(ai_data["articles"]):
        if "title_cn" not in article:
            article["title_cn"] = f"新闻 {i + 1}"
        if "summary_cn" not in article:
            article["summary_cn"] = "暂无摘要"
        if "source_index" not in article:
            article["source_index"] = i + 1

    if "seo_summary" not in ai_data:
        ai_data["seo_summary"] = ai_data["title"]

    if "intro_paragraphs" not in ai_data:
        ai_data["intro_paragraphs"] = []

    if not isinstance(ai_data["editorial_notes"], dict):
        ai_data["editorial_notes"] = {"timeline": "", "risk_watch": ""}

    for key in ["timeline", "risk_watch"]:
        if key not in ai_data["editorial_notes"]:
            ai_data["editorial_notes"][key] = ""

    if not isinstance(ai_data["tags"], list):
        ai_data["tags"] = ["国际新闻", "全球动态"]

    return ai_data


def validate_news_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and filter news items."""
    valid_items = []

    for item in items:
        if not isinstance(item, dict):
            continue
        if not item.get("title"):
            continue
        if not item.get("link"):
            continue
        valid_items.append(item)

    if len(valid_items) < MIN_NEWS_ITEMS:
        raise ValueError(f"Need at least {MIN_NEWS_ITEMS} valid news items")

    return valid_items


def validate_image_candidate(candidate: dict[str, Any]) -> bool:
    """Validate if image candidate meets requirements."""
    from daily_news.config import MIN_IMAGE_WIDTH, MIN_IMAGE_HEIGHT

    if not candidate.get("src"):
        return False

    width = candidate.get("width", 0)
    height = candidate.get("height", 0)

    if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
        return False

    return True
