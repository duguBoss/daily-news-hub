"""AI content generation and translation."""
from __future__ import annotations

from typing import Any

from daily_news.api import parse_json_response, request_gemini_with_fallback
from daily_news.common import count_chinese_chars, sanitize_text
from daily_news.prompts import (
    build_article_selection_prompt,
    build_editorial_prompt,
    build_summary_prompt,
    build_translation_prompt,
)


def translate_news_items(
    api_key: str, news_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Translate news titles and summaries to Chinese."""
    translated = []

    for item in news_items:
        prompt = build_translation_prompt(item["title"], item.get("summary", ""))

        try:
            response = request_gemini_with_fallback(api_key, prompt)
            data = parse_json_response(response)

            translated.append({
                "index": item["index"],
                "title": item["title"],
                "title_cn": data.get("title_cn", item["title"]),
                "summary_cn": data.get("summary_cn", item.get("summary", "")),
                "source_index": item["index"],
            })
        except Exception as e:
            print(f"Translation failed for {item['title']}: {e}")
            translated.append({
                "index": item["index"],
                "title": item["title"],
                "title_cn": item["title"],
                "summary_cn": item.get("summary", ""),
                "source_index": item["index"],
            })

    return translated


def generate_article_summary(
    api_key: str, title: str, content: str, previous: str = "", feedback: str = ""
) -> str:
    """Generate article summary with retry logic."""
    prompt = build_summary_prompt(title, content)

    if previous:
        prompt += f"\n\n之前生成的内容：\n{previous}\n\n"
        if feedback:
            prompt += f"调整要求：{feedback}\n"
        prompt += "请基于之前的内容进行调整，生成符合要求的新版本。"

    response = request_gemini_with_fallback(api_key, prompt, temperature=0.6)
    summary = sanitize_text(response)

    char_count = count_chinese_chars(summary)
    if char_count < 350:
        if previous:
            return generate_article_summary(
                api_key, title, content, summary, f"当前字数{char_count}，需要扩充到400-500字"
            )
    elif char_count > 550:
        if previous:
            return generate_article_summary(
                api_key, title, content, summary, f"当前字数{char_count}，需要精简到400-500字"
            )

    return summary


def build_ai_data_from_articles(
    api_key: str,
    translated_articles: list[dict[str, Any]],
    news_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build AI-generated editorial content."""
    articles_text = "\n\n".join(
        f"[{a['index']}] {a['title_cn']}\n{a['summary_cn'][:300]}"
        for a in translated_articles[:12]
    )

    selection_prompt = build_article_selection_prompt(articles_text)
    selection_response = request_gemini_with_fallback(api_key, selection_prompt)
    selection_data = parse_json_response(selection_response)
    selected_indices = selection_data.get("selected_indices", list(range(1, 7)))

    selected_articles = []
    for idx in selected_indices[:6]:
        for article in translated_articles:
            if article["index"] == idx:
                summary = generate_article_summary(
                    api_key, article["title"], article.get("summary_cn", "")
                )
                selected_articles.append({
                    "source_index": article["index"],
                    "title_cn": article["title_cn"],
                    "summary_cn": summary,
                })
                break

    editorial_prompt = build_editorial_prompt(articles_text)
    editorial_response = request_gemini_with_fallback(api_key, editorial_prompt)
    editorial_data = parse_json_response(editorial_response)

    return {
        "title": editorial_data.get("title", "全球简报"),
        "seo_summary": editorial_data.get("seo_summary", ""),
        "intro_paragraphs": editorial_data.get("intro_paragraphs", []),
        "articles": selected_articles,
        "editorial_notes": editorial_data.get("editorial_notes", {"timeline": "", "risk_watch": ""}),
        "tags": editorial_data.get("tags", ["国际新闻"]),
        "cover_source_index": selected_articles[0]["source_index"] if selected_articles else None,
    }


def build_fallback_ai_data(news_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Build fallback AI data when API fails."""
    articles = []
    for item in news_items[:6]:
        articles.append({
            "source_index": item["index"],
            "title_cn": item.get("title_cn", item["title"]),
            "summary_cn": item.get("summary_cn", item.get("summary", "")),
        })

    return {
        "title": "全球新闻简报",
        "seo_summary": "汇集全球重要新闻动态",
        "intro_paragraphs": [],
        "articles": articles,
        "editorial_notes": {"timeline": "今日全球新闻动态", "risk_watch": "持续关注国际形势"},
        "tags": ["国际新闻", "全球动态"],
        "cover_source_index": news_items[0]["index"] if news_items else None,
    }
