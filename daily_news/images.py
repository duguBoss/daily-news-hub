"""Image handling and download functions."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from daily_news.common import normalize_news_item_images
from daily_news.config import (
    ASSET_ROOT,
    MAX_IMAGE_DISCOVERY_ITEMS,
    MAX_IMAGES_PER_ARTICLE,
    MIN_IMAGE_HEIGHT,
    MIN_IMAGE_WIDTH,
    MIN_REQUIRED_ARTICLE_IMAGES,
    PLAYWRIGHT_TIMEOUT_MS,
    REQUEST_TIMEOUT,
)
from daily_news.image_processing import process_image_to_jpeg


def download_image(
    image_url: str,
    target_dir: Path,
    file_stem: str,
    referer: str = "",
) -> tuple[str, str]:
    """Download image, convert to JPEG, and compress if needed."""
    local_name = f"{file_stem}.jpg"
    local_path = target_dir / local_name

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    if referer:
        headers["Referer"] = referer

    response = requests.get(image_url, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    image_data = process_image_to_jpeg(response.content)
    local_path.write_bytes(image_data)

    return str(local_path), image_url


def choose_image_candidates(candidates: list[dict[str, Any]], max_count: int) -> list[dict[str, Any]]:
    """Select best image candidates from list."""
    valid = []
    for c in candidates:
        if not c.get("src"):
            continue
        width = c.get("width", 0)
        height = c.get("height", 0)
        if width >= MIN_IMAGE_WIDTH and height >= MIN_IMAGE_HEIGHT:
            valid.append(c)

    valid.sort(key=lambda x: x.get("width", 0) * x.get("height", 0), reverse=True)
    return valid[:max_count]


def enrich_news_images(
    news_items: list[dict[str, Any]],
    date_str: str,
    max_items: int = MAX_IMAGE_DISCOVERY_ITEMS,
    only_missing: bool = False,
) -> None:
    """Enrich news items with images using Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not available, skipping image enrichment")
        return

    target_dir = ASSET_ROOT / date_str
    target_dir.mkdir(parents=True, exist_ok=True)

    items_to_process = [
        item for item in news_items[:max_items]
        if not only_missing or not item.get("image_urls")
    ]

    if not items_to_process:
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0",
        )

        for item in items_to_process:
            if not item.get("resolved_url"):
                continue

            try:
                page = context.new_page()
                page.goto(item["resolved_url"], timeout=PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)

                candidates = page.evaluate("""() => {
                    const urls = [];
                    const push = (src, width, height) => {
                        if (!src) return;
                        try {
                            const absolute = new URL(src, document.baseURI).href;
                            urls.push({src: absolute, width: width || 0, height: height || 0});
                        } catch (e) {}
                    };
                    document.querySelectorAll('meta[property*="image"]').forEach(n => push(n.content, 1600, 900));
                    document.querySelectorAll('img').forEach(img => {
                        push(img.currentSrc || img.src, img.naturalWidth, img.naturalHeight);
                    });
                    return urls;
                }""")

                best = choose_image_candidates(candidates, MAX_IMAGES_PER_ARTICLE)

                for idx, candidate in enumerate(best, 1):
                    try:
                        from daily_news.common import slugify
                        stem = f"{item['index']:02d}-{idx}-{slugify(item['title'])}"
                        path, url = download_image(
                            candidate["src"], target_dir, stem, item["resolved_url"]
                        )
                        item["image_paths"].append(path)
                        item["image_urls"].append(url)
                        if not item.get("image_url"):
                            item["image_url"] = url
                    except Exception as e:
                        print(f"Failed to download image: {e}")

                normalize_news_item_images(item)
                page.close()

            except Exception as e:
                print(f"Failed to enrich images for {item.get('title', 'unknown')}: {e}")

        context.close()
        browser.close()


def ensure_minimum_article_images(
    news_items: list[dict[str, Any]], date_str: str
) -> None:
    """Ensure minimum number of articles have images."""
    from daily_news.common import count_news_items_with_images

    current = count_news_items_with_images(news_items)
    if current >= MIN_REQUIRED_ARTICLE_IMAGES:
        return

    limits = [
        max(MAX_IMAGE_DISCOVERY_ITEMS, MIN_REQUIRED_ARTICLE_IMAGES * 4),
        min(len(news_items), max(MAX_IMAGE_DISCOVERY_ITEMS * 2, MIN_REQUIRED_ARTICLE_IMAGES * 8)),
        len(news_items),
    ]

    for limit in limits:
        if current >= MIN_REQUIRED_ARTICLE_IMAGES:
            break
        enrich_news_images(news_items, date_str, limit, only_missing=True)
        current = count_news_items_with_images(news_items)
        print(f"Image coverage: {current}/{MIN_REQUIRED_ARTICLE_IMAGES} (scanned {limit})")

    if current < MIN_REQUIRED_ARTICLE_IMAGES:
        raise RuntimeError(f"Not enough images: {current}/{MIN_REQUIRED_ARTICLE_IMAGES}")
