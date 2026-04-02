"""Card content generation step."""
from __future__ import annotations

from typing import Any

from daily_news.common import count_chinese_chars
from daily_news.config import MAX_CARD_RETRIES
from daily_news.models import (
    build_model_candidates,
    is_quota_or_rate_limit_error,
    parse_model_json,
)
from daily_news.prompts import build_article_card_prompt
from daily_news.rewrite_prompts import build_card_rewrite_prompt


def _validate_card_content(content: dict[str, Any]) -> tuple[bool, list[int]]:
    """Validate card content has proper paragraph lengths.

    Returns (is_valid, paragraph_lengths).
    """
    paragraphs = content.get("paragraphs", [])
    if len(paragraphs) != 2:
        return False, []

    lengths = []
    for para in paragraphs:
        length = count_chinese_chars(para)
        lengths.append(length)
        if not (200 <= length <= 300):
            return False, lengths

    return True, lengths


def generate_card_step(
    api_key: str,
    card_number: int,
    article: dict[str, Any],
    date_str: str,
) -> dict[str, Any]:
    """Step 2/3: Generate content for a single card with retry logic."""
    prompt = build_article_card_prompt(card_number, article, date_str)
    candidates = build_model_candidates(api_key)

    previous_attempts: list[dict[str, Any]] = []

    for provider, model_name, provider_api_key, caller in candidates:
        print(f"[Step 2/3] Card {card_number} using {provider}:{model_name}")

        for attempt in range(MAX_CARD_RETRIES):
            try:
                print(f"  Attempt {attempt + 1}/{MAX_CARD_RETRIES}")

                # Use rewrite prompt if we have previous attempts
                if previous_attempts:
                    last_attempt = previous_attempts[-1]
                    _, last_lengths = _validate_card_content(last_attempt)
                    current_prompt = build_card_rewrite_prompt(
                        card_number, article, date_str, last_attempt, last_lengths
                    )
                else:
                    current_prompt = prompt

                raw = caller(provider_api_key, current_prompt, model_name)
                raw = raw.strip()

                # Parse JSON response
                try:
                    content = parse_model_json(raw)
                except Exception as e:
                    print(f"  ✗ JSON parse failed: {e}")
                    continue

                # Validate content
                is_valid, lengths = _validate_card_content(content)

                if is_valid:
                    print(f"[Step 2/3] Card {card_number} generated: {sum(lengths)} chars")
                    return content
                else:
                    print(f"  ✗ Length check failed: {lengths}, retrying...")
                    previous_attempts.append(content)
                    continue

            except Exception as e:
                print(f"  ✗ API failed: {e}")
                if is_quota_or_rate_limit_error(str(e)):
                    print(f"  Switching to next model...")
                    break
                continue

    # Fallback: return basic content
    print(f"[Step 2/3] Card {card_number} using fallback")
    return {
        "title": article.get("title_cn", article.get("title", "")),
        "paragraphs": [
            article.get("summary_cn", article.get("summary", ""))[:250],
            "（内容生成失败，使用摘要替代）",
        ],
    }


def generate_editorial_step(
    api_key: str,
    articles: list[dict[str, Any]],
    date_str: str,
) -> dict[str, Any]:
    """Step 3: Generate editorial notes."""
    from daily_news.prompts import build_editorial_notes_prompt

    prompt = build_editorial_notes_prompt(articles, date_str)
    candidates = build_model_candidates(api_key)

    for provider, model_name, provider_api_key, caller in candidates:
        print(f"[Step 3/3] Editorial using {provider}:{model_name}")

        try:
            raw = caller(provider_api_key, prompt, model_name)
            content = parse_model_json(raw.strip())

            return {
                "timeline": content.get("timeline", "今日全球新闻动态"),
                "risk_watch": content.get("risk_watch", "持续关注国际形势"),
                "tags": content.get("tags", ["国际新闻", "全球动态"]),
            }
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            continue

    # Fallback
    return {
        "timeline": "今日全球新闻动态",
        "risk_watch": "持续关注国际形势",
        "tags": ["国际新闻", "全球动态"],
    }
