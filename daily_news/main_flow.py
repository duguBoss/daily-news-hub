"""Main workflow orchestration."""
from __future__ import annotations

from daily_news.ai_content import build_fallback_ai_data, generate_ai_content
from daily_news.common import format_date, now_shanghai, require_api_key
from daily_news.config import SHANGHAI_TZ
from daily_news.feed import collect_news_items, fetch_feed
from daily_news.images import ensure_minimum_article_images
from daily_news.output import clean_all_generated_files, save_outputs
from daily_news.validation import validate_ai_data


def run_daily_news_workflow() -> str:
    """Execute the complete daily news workflow."""
    clean_all_generated_files()

    api_key = require_api_key()

    feed = fetch_feed()
    news_items = collect_news_items(feed)

    date_str = format_date()
    ensure_minimum_article_images(news_items, date_str)

    try:
        ai_data = generate_ai_content(api_key, news_items, date_str)
        ai_data = validate_ai_data(ai_data, news_items)
    except Exception as exc:
        print(f"AI generation failed, using fallback: {exc}")
        ai_data = validate_ai_data(build_fallback_ai_data(news_items), news_items)

    output_file = save_outputs(ai_data, news_items)
    print(f"Generated daily briefing: {output_file}")

    return output_file


def main() -> None:
    """Entry point."""
    run_daily_news_workflow()


if __name__ == "__main__":
    main()
