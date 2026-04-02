"""Output file generation and cleanup."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from daily_news.common import now_shanghai, sanitize_image_url_list
from daily_news.config import MIN_REQUIRED_ARTICLE_IMAGES, SHANGHAI_TZ
from daily_news.rendering import attach_article_images, render_html, render_markdown


def save_outputs(
    ai_data: dict[str, Any], news_items: list[dict[str, Any]]
) -> str:
    """Save output files (JSON and Markdown)."""
    current_time = now_shanghai().strftime("%Y-%m-%d %H:%M:%S")
    cover_url = attach_article_images(ai_data, news_items)

    html_content = render_html(ai_data, news_items, cover_url, current_time)
    markdown_content = render_markdown(ai_data, news_items, cover_url, current_time)

    peitu_urls: list[str] = []
    seen: set[str] = set()
    for article in ai_data.get("articles", []):
        urls = sanitize_image_url_list(article.get("image_urls", []))
        if urls and urls[0] not in seen:
            seen.add(urls[0])
            peitu_urls.append(urls[0])

    if len(peitu_urls) < MIN_REQUIRED_ARTICLE_IMAGES:
        raise RuntimeError(
            f"Need at least {MIN_REQUIRED_ARTICLE_IMAGES} images, got {len(peitu_urls)}"
        )

    final_output = {
        "title": ai_data["title"],
        "seo_summary": ai_data.get("seo_summary", ""),
        "url": "",
        "cover": cover_url,
        "peitu_url": peitu_urls,
        "wechat_html": html_content,
        "intro_paragraphs": ai_data.get("intro_paragraphs", []),
        "articles": ai_data["articles"],
        "editorial_notes": ai_data.get("editorial_notes", {}),
        "tags": ai_data.get("tags", []),
        "generated_at": current_time,
        "is_daily_featured": True,
        "source_count": len(news_items),
        "image_count": sum(len(item.get("image_urls", [])) for item in news_items),
        "sources": news_items,
    }

    date_str = now_shanghai().strftime("%Y-%m-%d")
    json_file = f"Daily_News_{date_str}.json"
    md_file = f"Daily_News_{date_str}.md"

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return json_file


def clean_old_files(days_to_keep: int = 1) -> None:
    """Clean old output files."""
    cutoff = now_shanghai() - timedelta(days=days_to_keep)

    for pattern in ["Daily_News_*.md", "Daily_News_*.json"]:
        for file_path in Path(".").glob(pattern):
            date_str = file_path.stem.replace("Daily_News_", "")
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=SHANGHAI_TZ)
                if file_date < cutoff:
                    file_path.unlink()
                    print(f"Deleted old file: {file_path}")
            except ValueError:
                continue

    assets_dir = Path("assets") / "generated"
    if assets_dir.exists():
        for date_dir in assets_dir.iterdir():
            if date_dir.is_dir():
                try:
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d").replace(tzinfo=SHANGHAI_TZ)
                    if dir_date < cutoff:
                        shutil.rmtree(date_dir)
                        print(f"Deleted old directory: {date_dir}")
                except ValueError:
                    continue


def clean_all_generated_files() -> None:
    """Clean all generated files before new execution."""
    patterns = ["Daily_News_*.md", "Daily_News_*.json"]
    deleted_count = 0

    for pattern in patterns:
        for file_path in Path(".").glob(pattern):
            try:
                file_path.unlink()
                print(f"Deleted: {file_path}")
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")

    assets_dir = Path("assets") / "generated"
    if assets_dir.exists():
        for date_dir in assets_dir.iterdir():
            if date_dir.is_dir():
                try:
                    shutil.rmtree(date_dir)
                    print(f"Deleted assets: {date_dir}")
                    deleted_count += 1
                except Exception as e:
                    print(f"Failed to delete {date_dir}: {e}")

    if deleted_count == 0:
        print("No existing generated files to clean")
    else:
        print(f"Cleaned {deleted_count} generated files/directories")
