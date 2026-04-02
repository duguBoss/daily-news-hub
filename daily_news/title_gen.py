"""Title generation step."""
from __future__ import annotations

import re
from typing import Any

from daily_news.common import count_chinese_chars
from daily_news.config import MAX_TITLE_RETRIES
from daily_news.models import build_model_candidates
from daily_news.prompts import build_title_prompt


def _is_valid_chinese_title(title: str) -> bool:
    """Check if title is valid Chinese title (20-30 chars, mostly Chinese)."""
    if not title:
        return False

    title_no_punct = re.sub(r"[^\u4e00-\u9fff\w]", "", title)
    char_count = len(title_no_punct)

    if not (20 <= char_count <= 30):
        return False

    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", title))
    return chinese_chars >= char_count * 0.8


def generate_title_step(
    api_key: str,
    date_str: str,
    articles: list[dict[str, Any]],
    recent_titles: list[str],
) -> tuple[str, str, str]:
    """Step 1: Generate title only. Returns (title, provider, model)."""
    prompt = build_title_prompt(date_str, articles, recent_titles)
    candidates = build_model_candidates(api_key)

    for provider, model_name, provider_api_key, caller in candidates:
        print(f"[Step 1/3] Using {provider}:{model_name}")

        for attempt in range(MAX_TITLE_RETRIES):
            try:
                print(f"  Attempt {attempt + 1}/{MAX_TITLE_RETRIES}")
                raw = caller(provider_api_key, prompt, model_name)
                title = raw.strip().strip('"').strip("'")

                if _is_valid_chinese_title(title):
                    print(f"[Step 1/3] ✓ Title generated ({len(title)} chars): {title[:40]}...")
                    return title, provider, model_name
                else:
                    title_no_punct = re.sub(r"[^\u4e00-\u9fff\w]", "", title)
                    char_count = len(title_no_punct)
                    chinese_count = count_chinese_chars(title)
                    if not (20 <= char_count <= 30):
                        print(f"  ✗ Rejected (length {char_count}, need 20-30), retrying...")
                    else:
                        print(f"  ✗ Rejected (only {chinese_count}/{char_count} Chinese), retrying...")
                    continue

            except Exception as e:
                print(f"  ✗ API failed: {e}")
                print(f"  Switching to next model...")
                break

    raise RuntimeError(
        f"Failed to generate valid title after trying all models. "
        f"Title must be 20-30 Chinese characters."
    )
