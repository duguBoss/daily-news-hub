"""AI content generation with step-by-step approach."""
from __future__ import annotations

from typing import Any

from daily_news.card_gen import generate_card_step, generate_editorial_step
from daily_news.title_gen import generate_title_step


def generate_ai_content(
    api_key: str,
    news_items: list[dict[str, Any]],
    date_str: str,
    recent_titles: list[str] | None = None,
) -> dict[str, Any]:
    """Generate complete AI content with step-by-step approach.

    Steps:
    1. Generate main title
    2. Generate content for each selected article
    3. Generate editorial notes
    """
    if recent_titles is None:
        recent_titles = []

    # Select top articles (up to 5)
    selected_articles = news_items[:5]

    # Step 1: Generate title
    title, _, _ = generate_title_step(api_key, date_str, selected_articles, recent_titles)

    # Step 2: Generate content for each article
    articles_data = []
    for i, article in enumerate(selected_articles, 1):
        card_content = generate_card_step(api_key, i, article, date_str)
        articles_data.append({
            "source_index": article.get("index", i),
            "title_cn": card_content["title"],
            "paragraphs": card_content["paragraphs"],
            "summary_cn": "\n\n".join(card_content["paragraphs"]),
            "image_urls": article.get("image_urls", []),
        })

    # Step 3: Generate editorial notes
    editorial = generate_editorial_step(api_key, selected_articles, date_str)

    return {
        "title": title,
        "seo_summary": f"{title} - {editorial['timeline'][:80]}",
        "intro_paragraphs": [],
        "articles": articles_data,
        "editorial_notes": {
            "timeline": editorial["timeline"],
            "risk_watch": editorial["risk_watch"],
        },
        "tags": editorial["tags"],
        "cover_source_index": articles_data[0]["source_index"] if articles_data else None,
    }


def build_fallback_ai_data(news_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Build fallback AI data when API fails."""
    articles = []
    for i, item in enumerate(news_items[:5], 1):
        summary = item.get("summary_cn", item.get("summary", ""))
        # Split summary into two parts for paragraphs
        mid = len(summary) // 2 if summary else 0
        para1 = summary[:mid] if mid > 100 else summary[:250]
        para2 = summary[mid:] if mid > 100 else "（详细内容待补充）"

        articles.append({
            "source_index": item.get("index", i),
            "title_cn": item.get("title_cn", item.get("title", "")),
            "paragraphs": [para1, para2],
            "summary_cn": summary,
            "image_urls": item.get("image_urls", []),
        })

    return {
        "title": "全球新闻简报",
        "seo_summary": "汇集全球重要新闻动态",
        "intro_paragraphs": [],
        "articles": articles,
        "editorial_notes": {"timeline": "今日全球新闻动态", "risk_watch": "持续关注国际形势"},
        "tags": ["国际新闻", "全球动态"],
        "cover_source_index": news_items[0].get("index", 1) if news_items else None,
    }
