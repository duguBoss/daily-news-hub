"""HTML and Markdown rendering functions."""
from __future__ import annotations

import html
from typing import Any

from daily_news.common import normalize_news_item_images, sanitize_image_url_list
from daily_news.config import BOTTOM_BANNER_URL, FALLBACK_COVER_URL, TOP_BANNER_URL
from daily_news.templates import (
    HTML_ARTICLE_END,
    HTML_ARTICLE_IMAGE,
    HTML_ARTICLE_START,
    HTML_EDITORIAL,
    HTML_HEADER,
    HTML_PARAGRAPH,
    HTML_TAG,
    HTML_TAGS_START,
    HTML_WRAPPER_END,
    HTML_WRAPPER_START,
    MD_ARTICLE_HEADER,
    MD_ARTICLE_IMAGE,
    MD_EDITORIAL_HEADER,
    MD_HEADER,
    MD_RISK_WATCH,
    MD_SOURCE_ITEM,
    MD_SOURCES_HEADER,
    MD_TAGS,
    MD_TIMELINE,
)


def render_html(
    ai_data: dict[str, Any],
    news_items: list[dict[str, Any]],
    cover_url: str,
    generated_at: str,
) -> str:
    """Render HTML content for WeChat."""
    parts = [
        HTML_WRAPPER_START.format(top_banner=TOP_BANNER_URL),
        HTML_HEADER.format(title=html.escape(ai_data["title"])),
    ]

    for article in ai_data.get("articles", []):
        parts.append(HTML_ARTICLE_START.format(title=html.escape(article["title_cn"])))

        image_urls = article.get("image_urls", [])
        if image_urls:
            parts.append(HTML_ARTICLE_IMAGE.format(url=html.escape(image_urls[0])))

        parts.append(HTML_PARAGRAPH.format(text=html.escape(article["summary_cn"])))
        parts.append(HTML_ARTICLE_END)

    notes = ai_data.get("editorial_notes", {})
    parts.append(
        HTML_EDITORIAL.format(
            timeline=html.escape(notes.get("timeline", "")),
            risk_watch=html.escape(notes.get("risk_watch", "")),
        )
    )

    parts.append(HTML_TAGS_START)
    for tag in ai_data.get("tags", []):
        parts.append(HTML_TAG.format(tag=html.escape(tag)))

    parts.append(HTML_WRAPPER_END.format(bottom_banner=BOTTOM_BANNER_URL))

    return "".join(parts)


def render_markdown(
    ai_data: dict[str, Any],
    news_items: list[dict[str, Any]],
    cover_url: str,
    generated_at: str,
) -> str:
    """Render Markdown content."""
    lines = [MD_HEADER.format(title=ai_data["title"])]

    for article in ai_data.get("articles", []):
        lines.append(MD_ARTICLE_HEADER.format(title=article.get("title_cn", "Untitled")))
        if article.get("image_urls"):
            lines.append(MD_ARTICLE_IMAGE.format(url=article["image_urls"][0]))
        lines.append(article.get("summary_cn", ""))
        lines.append("")

    notes = ai_data.get("editorial_notes", {})
    lines.append(MD_EDITORIAL_HEADER)
    lines.append(MD_TIMELINE.format(timeline=notes.get("timeline", "")))
    lines.append(MD_RISK_WATCH.format(risk_watch=notes.get("risk_watch", "")))
    lines.append("")
    lines.append(MD_SOURCES_HEADER)

    for item in news_items:
        source = item.get("resolved_url") or item.get("google_news_url", "")
        lines.append(
            MD_SOURCE_ITEM.format(
                index=item.get("index", 0),
                title=item.get("title", ""),
                url=source,
            )
        )

    tags = ai_data.get("tags", [])
    lines.append(MD_TAGS.format(tags=" / ".join(tags)))
    return "\n".join(lines)


def attach_article_images(
    ai_data: dict[str, Any], news_items: list[dict[str, Any]]
) -> str:
    """Attach images to articles and return cover URL."""
    news_by_index = {item["index"]: item for item in news_items}
    selected_cover = ""

    cover_idx = ai_data.get("cover_source_index")
    if cover_idx:
        cover_item = news_by_index.get(cover_idx)
        if cover_item:
            normalize_news_item_images(cover_item)
            if cover_item.get("image_url"):
                selected_cover = cover_item["image_url"]

    if not selected_cover:
        for item in news_items:
            normalize_news_item_images(item)
            if item.get("image_urls"):
                selected_cover = item["image_urls"][0]
                break

    for article in ai_data.get("articles", []):
        item = news_by_index.get(article.get("source_index", 0))
        if not item:
            continue
        normalize_news_item_images(item)
        article["image_urls"] = item.get("image_urls", [])[:]
        article["image_caption"] = item.get("title", "")
        article["original_title"] = item.get("title", "")
        article["original_url"] = item.get("resolved_url") or item.get("google_news_url", "")

    return selected_cover or FALLBACK_COVER_URL
