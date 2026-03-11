from __future__ import annotations

import datetime
import hashlib
import html
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import feedparser
import pytz
import requests

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightTimeoutError = RuntimeError
    sync_playwright = None


RSS_URL = "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"
NEWS_SOURCE_URL = (
    "https://news.google.com/topics/"
    "CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx1YlY4U0JXVnVMVWRDR2dKRFFTZ0FQAQ"
    "?hl=en-US&gl=US&ceid=US%3Aen"
)
DEFAULT_REPOSITORY = "duguBoss/daily-news-hub"
DEFAULT_BRANCH = "main"
MODEL_NAME = "gemini-3.1-flash-lite-preview"
REQUEST_TIMEOUT = 30
PLAYWRIGHT_TIMEOUT_MS = 25000
MAX_NEWS_ITEMS = 36
MIN_NEWS_ITEMS = 10
MAX_IMAGE_DISCOVERY_ITEMS = 12
MAX_DOWNLOADED_IMAGES = 8
MIN_IMAGE_WIDTH = 360
MIN_IMAGE_HEIGHT = 200
SHANGHAI_TZ = pytz.timezone("Asia/Shanghai")
ASSET_ROOT = Path("assets") / "generated"

TOP_BANNER_URL = (
    "https://mmbiz.qpic.cn/mmbiz_gif/"
    "3hAJnwuyZuicicZkgJBUCCaricdibomDBrTzXgUR7FJnf11qGIo8nmKt6RxibXrb5s4RFb9UZ9UOHQy7fqQyI377Licw/"
    "0?wx_fmt=gif"
)
BOTTOM_BANNER_URL = (
    "https://mmbiz.qpic.cn/mmbiz_gif/"
    "3hAJnwuyZuicicZkgJBUCCaricdibomDBrTzk57DCmhVC16o9ILH0Tn1YPEiarfLRRQSVFN2mJdeYibGnBPialPIzvojw/"
    "0?wx_fmt=gif"
)
FALLBACK_COVER_URL = (
    "https://raw.githubusercontent.com/duguBoss/daily-renzhi-hub/main/assets/rss_covers/"
    "93a57b73c1977bb9.png"
)

CHINA_RELATED_PATTERNS = [
    r"\bchina\b",
    r"\bchinese\b",
    r"\bbeijing\b",
    r"\bshanghai\b",
    r"\bhong kong\b",
    r"\bmacau\b",
    r"\bxi jinping\b",
    r"\btaiwan\b",
    r"\btaipei\b",
]


def require_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY. Set it in the environment or GitHub Secrets.")
    return api_key


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug[:60] or "news"


def fetch_feed() -> Any:
    response = requests.get(
        RSS_URL,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "daily-news-hub/1.0"},
    )
    response.raise_for_status()
    return feedparser.parse(response.content)


def is_china_related(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in CHINA_RELATED_PATTERNS)


def collect_news_items(feed: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for entry in feed.entries:
        title = normalize_whitespace(entry.get("title", ""))
        summary = normalize_whitespace(re.sub(r"<[^>]+>", " ", entry.get("summary", "")))
        google_news_url = entry.get("link", "")
        combined = " ".join(part for part in [title, summary] if part)

        if not title or is_china_related(combined):
            continue

        items.append(
            {
                "index": len(items) + 1,
                "title": title,
                "summary": summary[:240],
                "google_news_url": google_news_url,
                "resolved_url": "",
                "image_url": "",
                "image_path": "",
                "image_source": "",
                "image_caption": "",
            }
        )

        if len(items) >= MAX_NEWS_ITEMS:
            break

    if len(items) < MIN_NEWS_ITEMS:
        raise RuntimeError(
            f"Usable news items after filtering are too few: {len(items)}. Need at least {MIN_NEWS_ITEMS}."
        )

    return items


def build_prompt(news_items: list[dict[str, Any]]) -> str:
    news_lines = []
    for item in news_items:
        line = f"{item['index']}. 标题：{item['title']}"
        if item["summary"]:
            line += f"；摘要：{item['summary']}"
        if item["resolved_url"]:
            line += f"；原文链接：{item['resolved_url']}"
        news_lines.append(line)

    news_text = "\n".join(news_lines)

    return f"""
你是一个严格客观的国际新闻编辑系统。输入是 Google News WORLD 频道中经过初筛的英文新闻标题、摘要和部分原文链接。
请输出一份适合微信公众号发布的国际宏观日报，使用简体中文。

硬约束：
1. 只陈述事实和趋势，不写主观评价，不煽情，不夸张。
2. 任何与中国相关的信息都必须排除，包括中国大陆、香港、澳门、台湾，以及中国企业和中国政治人物。
3. 内容范围仅限：国际地缘局势、全球宏观经济、国际科技与商业、能源与供应链、重大自然灾害与公共安全。
4. 尽量全面，覆盖多个板块，不要只聚焦单一事件。
5. 如果某个板块素材不足，不要编造。
6. 输出内容要像正式成稿，不要出现“可能”“或许”“根据标题推测”等措辞。

输出要求：
1. 只返回合法 JSON，不要输出 markdown 代码块，不要输出解释。
2. JSON 必须严格符合以下结构：
{{
  "title": "一个偏国际媒体风格的主标题，不超过22字",
  "seo_summary": "90到120字摘要",
  "cover_source_index": 1,
  "intro_paragraphs": [
    "第一段导语，70到110字",
    "第二段导语，70到110字"
  ],
  "categories": [
    {{
      "name": "分类名称",
      "summary": "该分类的一句话提要，40到70字",
      "source_indexes": [1, 2],
      "paragraphs": [
        "第1段，70到120字",
        "第2段，70到120字"
      ]
    }}
  ],
  "bullet_briefs": [
    "5到8条简报，每条 28到45 字"
  ],
  "editorial_notes": {{
    "timeline": "一句话描述今天国际新闻节奏，30到50字",
    "risk_watch": "一句话描述接下来值得关注的风险点，30到50字"
  }},
  "tags": ["国际新闻", "全球经济", "地缘局势", "科技商业", "能源供应"]
}}

进一步约束：
1. categories 必须是 4 到 5 个分类。
2. 每个分类必须包含 summary、source_indexes、paragraphs。
3. source_indexes 必须引用下面素材编号中的 1 到 36，且每个分类给出 1 到 2 个编号。
4. 如果没有合适编号，也要尽量选择最接近该分类的素材编号。
5. bullet_briefs 至少 5 条，最多 8 条。
6. tags 固定输出 5 个。

以下是今日素材：
{news_text}
""".strip()


def call_gemini(api_key: str, prompt: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL_NAME}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.35,
            "topP": 0.9,
            "responseMimeType": "application/json",
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_LOW_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_LOW_AND_ABOVE"},
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_LOW_AND_ABOVE",
            },
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_LOW_AND_ABOVE"},
        ],
    }

    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Gemini API request failed with status {response.status_code}: {response.text}"
        )

    result_json = response.json()
    try:
        return result_json["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response shape: {result_json}") from exc


def parse_model_json(raw_text: str) -> dict[str, Any]:
    cleaned_text = re.sub(r"^```json\s*", "", raw_text.strip(), flags=re.IGNORECASE)
    cleaned_text = re.sub(r"\s*```$", "", cleaned_text).strip()

    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Model response is not valid JSON: {cleaned_text}") from exc


def ensure_list_of_strings(value: Any, field_name: str, min_items: int = 1) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list.")

    cleaned = [normalize_whitespace(str(item)) for item in value if str(item).strip()]
    if len(cleaned) < min_items:
        raise ValueError(f"{field_name} requires at least {min_items} items.")
    return cleaned


def normalize_source_indexes(value: Any, max_index: int) -> list[int]:
    if not isinstance(value, list):
        return []

    indexes: list[int] = []
    for item in value:
        try:
            index = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= index <= max_index and index not in indexes:
            indexes.append(index)
    return indexes[:2]


def validate_ai_data(ai_data: dict[str, Any], news_items: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(ai_data, dict):
        raise ValueError("Model output is not a JSON object.")

    title = normalize_whitespace(str(ai_data.get("title", "今日国际宏观观察")))
    seo_summary = normalize_whitespace(
        str(
            ai_data.get(
                "seo_summary",
                "聚焦国际局势、全球经济、科技产业与重大风险事件的每日要点。",
            )
        )
    )
    intro_paragraphs = ensure_list_of_strings(
        ai_data.get("intro_paragraphs", []), "intro_paragraphs", min_items=2
    )[:2]
    bullet_briefs = ensure_list_of_strings(
        ai_data.get("bullet_briefs", []), "bullet_briefs", min_items=5
    )[:8]
    tags = ensure_list_of_strings(ai_data.get("tags", []), "tags", min_items=5)[:5]

    raw_notes = ai_data.get("editorial_notes", {})
    if not isinstance(raw_notes, dict):
        raise ValueError("editorial_notes must be an object.")

    editorial_notes = {
        "timeline": normalize_whitespace(
            str(raw_notes.get("timeline", "国际焦点沿地缘、安全与市场链条连续展开。"))
        ),
        "risk_watch": normalize_whitespace(
            str(raw_notes.get("risk_watch", "关注局势外溢对能源、物流和金融定价的影响。"))
        ),
    }

    categories = []
    raw_categories = ai_data.get("categories", [])
    if not isinstance(raw_categories, list) or len(raw_categories) < 4:
        raise ValueError("categories must contain at least 4 items.")

    max_index = len(news_items)
    for raw_category in raw_categories[:5]:
        if not isinstance(raw_category, dict):
            continue

        name = normalize_whitespace(str(raw_category.get("name", "国际焦点")))
        summary = normalize_whitespace(str(raw_category.get("summary", "")))
        paragraphs = ensure_list_of_strings(
            raw_category.get("paragraphs", []), f"{name}.paragraphs", min_items=2
        )[:2]
        source_indexes = normalize_source_indexes(raw_category.get("source_indexes", []), max_index)

        if not name or not summary:
            continue

        categories.append(
            {
                "name": name,
                "summary": summary,
                "source_indexes": source_indexes,
                "paragraphs": paragraphs,
                "image_url": "",
                "image_caption": "",
                "image_source": "",
            }
        )

    if len(categories) < 4:
        raise ValueError("Effective categories are fewer than 4.")

    cover_source_index = 0
    try:
        candidate_cover_index = int(ai_data.get("cover_source_index", 0))
        if 1 <= candidate_cover_index <= max_index:
            cover_source_index = candidate_cover_index
    except (TypeError, ValueError):
        pass

    return {
        "title": title,
        "seo_summary": seo_summary,
        "cover_source_index": cover_source_index,
        "intro_paragraphs": intro_paragraphs,
        "categories": categories,
        "bullet_briefs": bullet_briefs,
        "editorial_notes": editorial_notes,
        "tags": tags,
    }


def score_image_candidate(candidate: dict[str, Any]) -> int:
    src = candidate.get("src", "")
    width = int(candidate.get("width") or 0)
    height = int(candidate.get("height") or 0)
    alt = candidate.get("alt", "").lower()

    score = 0
    score += min(width, 2400) // 20
    score += min(height, 1600) // 20
    if "og:" in candidate.get("source", ""):
        score += 200
    if "twitter" in candidate.get("source", ""):
        score += 160
    if "hero" in alt or "lead" in alt:
        score += 80
    if any(token in src.lower() for token in ["logo", "icon", "sprite", "avatar"]):
        score -= 250
    if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
        score -= 300
    return score


def choose_best_image_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    cleaned_candidates = []
    seen = set()

    for candidate in candidates:
        src = normalize_whitespace(str(candidate.get("src", "")))
        if not src or src in seen:
            continue
        seen.add(src)

        lowered = src.lower()
        if lowered.startswith("data:") or lowered.endswith(".svg"):
            continue

        cleaned_candidates.append(
            {
                "src": src,
                "width": int(candidate.get("width") or 0),
                "height": int(candidate.get("height") or 0),
                "alt": normalize_whitespace(str(candidate.get("alt", ""))),
                "source": normalize_whitespace(str(candidate.get("source", ""))),
            }
        )

    if not cleaned_candidates:
        return None

    cleaned_candidates.sort(key=score_image_candidate, reverse=True)
    best = cleaned_candidates[0]
    if score_image_candidate(best) < 0:
        return None
    return best


def guess_extension(image_url: str, content_type: str) -> str:
    if content_type:
        content_type = content_type.split(";")[0].strip().lower()
        if content_type == "image/jpeg":
            return ".jpg"
        guessed = mimetypes.guess_extension(content_type)
        if guessed:
            return guessed

    path = urlparse(image_url).path.lower()
    for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def raw_asset_url(relative_path: Path) -> str:
    repository = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY)
    branch = os.environ.get("GITHUB_REF_NAME", DEFAULT_BRANCH)
    normalized = relative_path.as_posix()
    return f"https://raw.githubusercontent.com/{repository}/{branch}/{normalized}"


def download_image(image_url: str, target_dir: Path, file_stem: str, referer: str) -> tuple[str, str]:
    response = requests.get(
        image_url,
        timeout=REQUEST_TIMEOUT,
        stream=True,
        headers={"User-Agent": "daily-news-hub/1.0", "Referer": referer},
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    extension = guess_extension(image_url, content_type)
    content = response.content
    if len(content) < 15_000:
        raise ValueError("Downloaded image is too small.")

    digest = hashlib.sha1(content).hexdigest()[:12]
    filename = f"{file_stem}-{digest}{extension}"
    target_dir.mkdir(parents=True, exist_ok=True)
    relative_path = target_dir / filename
    relative_path.write_bytes(content)
    return str(relative_path.as_posix()), raw_asset_url(relative_path)


def enrich_news_images(news_items: list[dict[str, Any]], date_str: str) -> None:
    if not PLAYWRIGHT_AVAILABLE:
        print("Playwright is not installed. Skipping article image discovery.")
        return

    target_dir = ASSET_ROOT / date_str
    downloaded = 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_navigation_timeout(PLAYWRIGHT_TIMEOUT_MS)

        for item in news_items[:MAX_IMAGE_DISCOVERY_ITEMS]:
            if not item["google_news_url"]:
                continue

            try:
                page.goto(item["google_news_url"], wait_until="domcontentloaded")
                page.wait_for_timeout(1800)
                page.evaluate("window.scrollTo(0, Math.min(document.body.scrollHeight * 0.35, 1200))")
                page.wait_for_timeout(600)
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue

            item["resolved_url"] = page.url
            if is_china_related(f"{item['title']} {item['resolved_url']}"):
                continue

            try:
                candidates = page.evaluate(
                    """() => {
                        const urls = [];
                        const push = (src, width, height, alt, source) => {
                            if (!src) return;
                            try {
                                const absolute = new URL(src, document.baseURI).href;
                                urls.push({ src: absolute, width: width || 0, height: height || 0, alt: alt || "", source });
                            } catch (e) {}
                        };

                        document.querySelectorAll('meta[property="og:image"], meta[property="og:image:secure_url"], meta[name="og:image"], meta[name="twitter:image"], meta[property="twitter:image"]').forEach((node) => {
                            push(node.content || "", 1600, 900, "", node.getAttribute("property") || node.getAttribute("name") || "meta");
                        });

                        document.querySelectorAll("img").forEach((img) => {
                            const rect = img.getBoundingClientRect();
                            const width = img.naturalWidth || rect.width || img.width || 0;
                            const height = img.naturalHeight || rect.height || img.height || 0;
                            push(img.currentSrc || img.src || "", width, height, img.alt || "", "img");
                        });

                        return urls;
                    }"""
                )
            except Exception:
                continue

            best_candidate = choose_best_image_candidate(candidates)
            if not best_candidate:
                continue

            try:
                image_path, image_url = download_image(
                    image_url=best_candidate["src"],
                    target_dir=target_dir,
                    file_stem=f"{item['index']:02d}-{slugify(item['title'])}",
                    referer=item["resolved_url"],
                )
            except Exception:
                continue

            item["image_url"] = image_url
            item["image_path"] = image_path
            item["image_source"] = best_candidate["src"]
            item["image_caption"] = item["title"]
            downloaded += 1

            if downloaded >= MAX_DOWNLOADED_IMAGES:
                break

        context.close()
        browser.close()


def attach_category_images(ai_data: dict[str, Any], news_items: list[dict[str, Any]]) -> str:
    news_by_index = {item["index"]: item for item in news_items}
    selected_cover = ""

    if ai_data["cover_source_index"]:
        cover_item = news_by_index.get(ai_data["cover_source_index"])
        if cover_item and cover_item["image_url"]:
            selected_cover = cover_item["image_url"]

    if not selected_cover:
        for item in news_items:
            if item["image_url"]:
                selected_cover = item["image_url"]
                break

    for category in ai_data["categories"]:
        for source_index in category["source_indexes"]:
            item = news_by_index.get(source_index)
            if item and item["image_url"]:
                category["image_url"] = item["image_url"]
                category["image_caption"] = item["title"]
                category["image_source"] = item["resolved_url"] or item["google_news_url"]
                break

    return selected_cover or FALLBACK_COVER_URL


def render_paragraph(text: str, extra_style: str = "") -> str:
    style = (
        "margin:0 0 18px 0;line-height:1.95;color:#1f2937;font-size:16px;"
        "letter-spacing:0.2px;text-align:justify;"
    )
    if extra_style:
        style += extra_style
    return f"<p style=\"{style}\">{html.escape(text)}</p>"


def render_category_image(category: dict[str, Any]) -> str:
    if not category["image_url"]:
        return ""

    source_line = ""
    if category["image_source"]:
        source_line = (
            f"<div style=\"margin-top:8px;font-size:12px;color:#6b7280;\">"
            f"图片来源：<a href=\"{html.escape(category['image_source'])}\" style=\"color:#6b7280;text-decoration:none;\">原文页面</a>"
            f"</div>"
        )

    return (
        "<section style=\"margin:0 0 18px 0;\">"
        f"<img src=\"{html.escape(category['image_url'])}\" style=\"width:100%;display:block;border-radius:2px;\">"
        f"<div style=\"margin-top:10px;font-size:13px;line-height:1.7;color:#4b5563;\">{html.escape(category['image_caption'] or category['name'])}</div>"
        f"{source_line}"
        "</section>"
    )


def render_html(
    ai_data: dict[str, Any],
    news_items: list[dict[str, Any]],
    cover_url: str,
    generated_at: str,
) -> str:
    title = html.escape(ai_data["title"])
    summary = html.escape(ai_data["seo_summary"])
    image_count = sum(1 for item in news_items if item["image_url"])

    parts = [
        "<section style=\"margin:0;padding:0;background:#ebe7df;\">",
        f"<img src=\"{TOP_BANNER_URL}\" style=\"width:100%;display:block;\">",
        (
            "<section style=\"max-width:760px;margin:0 auto;padding:0 20px 44px 20px;"
            "background:linear-gradient(180deg,#f5f0e8 0%,#fbfaf7 18%,#ffffff 100%);\">"
        ),
        (
            "<section style=\"padding:34px 0 20px 0;border-bottom:1px solid #d6d0c4;margin-bottom:24px;\">"
            "<div style=\"font-size:12px;letter-spacing:2px;color:#8b7d67;text-transform:uppercase;margin-bottom:12px;\">Global Briefing</div>"
            f"<h1 style=\"margin:0 0 14px 0;font-size:31px;line-height:1.25;color:#0f172a;font-weight:700;\">{title}</h1>"
            f"<p style=\"margin:0;font-size:15px;line-height:1.9;color:#4b5563;\">{summary}</p>"
            "</section>"
        ),
        (
            "<section style=\"display:flex;gap:10px;flex-wrap:wrap;margin:0 0 24px 0;font-size:12px;color:#6b7280;\">"
            f"<span style=\"padding:5px 10px;border:1px solid #d1d5db;background:#fff;\">北京时间 {html.escape(generated_at)}</span>"
            f"<span style=\"padding:5px 10px;border:1px solid #d1d5db;background:#fff;\">样本 {len(news_items)} 条</span>"
            f"<span style=\"padding:5px 10px;border:1px solid #d1d5db;background:#fff;\">配图 {image_count} 张</span>"
            "</section>"
        ),
        f"<img peitu=\"true\" src=\"{html.escape(cover_url)}\" style=\"width:100%;display:block;margin:0 0 26px 0;\">",
    ]

    for paragraph in ai_data["intro_paragraphs"]:
        parts.append(render_paragraph(paragraph))

    parts.append(
        "<section style=\"margin:26px 0 34px 0;padding:18px 20px;background:#f7f5f0;border-left:4px solid #111827;\">"
        "<div style=\"font-size:13px;letter-spacing:1.8px;color:#6b7280;text-transform:uppercase;margin-bottom:12px;\">News Briefs</div>"
    )
    for brief in ai_data["bullet_briefs"]:
        parts.append(
            "<div style=\"display:flex;align-items:flex-start;margin:0 0 12px 0;\">"
            "<span style=\"display:inline-block;width:6px;height:6px;background:#111827;border-radius:50%;margin:10px 10px 0 0;flex:0 0 auto;\"></span>"
            f"<span style=\"font-size:15px;line-height:1.8;color:#374151;\">{html.escape(brief)}</span>"
            "</div>"
        )
    parts.append("</section>")

    for category in ai_data["categories"]:
        parts.append(
            "<section style=\"margin:0 0 38px 0;\">"
            "<div style=\"display:flex;align-items:center;margin:0 0 14px 0;\">"
            "<span style=\"display:inline-block;width:36px;height:2px;background:#111827;margin-right:12px;\"></span>"
            f"<h2 style=\"margin:0;font-size:22px;color:#111827;letter-spacing:0.4px;\">{html.escape(category['name'])}</h2>"
            "</div>"
            f"<p style=\"margin:0 0 18px 0;font-size:14px;line-height:1.85;color:#6b7280;border-bottom:1px solid #e5e7eb;padding-bottom:14px;\">{html.escape(category['summary'])}</p>"
        )
        parts.append(render_category_image(category))
        for paragraph in category["paragraphs"]:
            parts.append(render_paragraph(paragraph))
        parts.append("</section>")

    parts.append(
        "<section style=\"margin:6px 0 34px 0;padding:22px 20px;background:#111827;color:#f9fafb;\">"
        "<div style=\"font-size:13px;letter-spacing:1.8px;text-transform:uppercase;color:#d1d5db;margin-bottom:12px;\">Risk Watch</div>"
        f"<p style=\"margin:0 0 10px 0;font-size:15px;line-height:1.8;color:#f3f4f6;\"><strong>节奏：</strong>{html.escape(ai_data['editorial_notes']['timeline'])}</p>"
        f"<p style=\"margin:0;font-size:15px;line-height:1.8;color:#f3f4f6;\"><strong>关注：</strong>{html.escape(ai_data['editorial_notes']['risk_watch'])}</p>"
        "</section>"
    )

    parts.append(
        "<section style=\"margin:0;padding-top:18px;border-top:1px solid #d1d5db;\">"
        "<div style=\"font-size:12px;letter-spacing:1.8px;color:#8b7d67;text-transform:uppercase;margin-bottom:12px;\">Keywords</div>"
    )
    for tag in ai_data["tags"]:
        parts.append(
            f"<span style=\"display:inline-block;margin:0 10px 10px 0;padding:6px 12px;border:1px solid #d1d5db;background:#fafaf9;color:#4b5563;font-size:12px;\">{html.escape(tag)}</span>"
        )
    parts.append("</section>")
    parts.append("</section>")
    parts.append(f"<img src=\"{BOTTOM_BANNER_URL}\" style=\"width:100%;display:block;\">")
    parts.append("</section>")
    return "".join(parts)


def render_markdown(
    ai_data: dict[str, Any],
    news_items: list[dict[str, Any]],
    cover_url: str,
    generated_at: str,
) -> str:
    lines = [
        f"# {ai_data['title']}",
        "",
        f"> 生成时间：{generated_at}（Asia/Shanghai）",
        f"> 封面图：{cover_url}",
        "",
        f"> {ai_data['seo_summary']}",
        "",
    ]

    for paragraph in ai_data["intro_paragraphs"]:
        lines.extend([paragraph, ""])

    lines.extend(["## 快讯", ""])
    for brief in ai_data["bullet_briefs"]:
        lines.append(f"- {brief}")
    lines.append("")

    for category in ai_data["categories"]:
        lines.extend([f"## {category['name']}", "", category["summary"], ""])
        if category["image_url"]:
            lines.append(f"配图：{category['image_url']}")
            if category["image_source"]:
                lines.append(f"原文：{category['image_source']}")
            lines.append("")
        for paragraph in category["paragraphs"]:
            lines.extend([paragraph, ""])

    lines.extend(
        [
            "## 编辑注",
            "",
            f"- 新闻节奏：{ai_data['editorial_notes']['timeline']}",
            f"- 风险观察：{ai_data['editorial_notes']['risk_watch']}",
            "",
            "## 原始素材",
            "",
        ]
    )

    for item in news_items:
        source_line = item["resolved_url"] or item["google_news_url"]
        lines.append(f"- [{item['index']}] {item['title']} | {source_line}")

    lines.extend(["", f"标签：{' / '.join(ai_data['tags'])}", ""])
    return "\n".join(lines)


def save_outputs(ai_data: dict[str, Any], news_items: list[dict[str, Any]]) -> str:
    now = datetime.datetime.now(SHANGHAI_TZ)
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    cover_url = attach_category_images(ai_data, news_items)
    html_content = render_html(ai_data, news_items, cover_url, current_time)
    markdown_content = render_markdown(ai_data, news_items, cover_url, current_time)

    final_output = {
        "title": ai_data["title"],
        "seo_summary": ai_data["seo_summary"],
        "url": NEWS_SOURCE_URL,
        "cover": cover_url,
        "wechat_html": html_content,
        "intro_paragraphs": ai_data["intro_paragraphs"],
        "categories": ai_data["categories"],
        "bullet_briefs": ai_data["bullet_briefs"],
        "editorial_notes": ai_data["editorial_notes"],
        "tags": ai_data["tags"],
        "generated_at": current_time,
        "is_daily_featured": True,
        "source_count": len(news_items),
        "image_count": sum(1 for item in news_items if item["image_url"]),
        "sources": news_items,
    }

    date_str = now.strftime("%Y-%m-%d")
    json_file_name = f"Daily_News_{date_str}.json"
    markdown_file_name = f"Daily_News_{date_str}.md"

    with open(json_file_name, "w", encoding="utf-8") as json_file:
        json.dump(final_output, json_file, ensure_ascii=False, indent=2)

    with open(markdown_file_name, "w", encoding="utf-8") as markdown_file:
        markdown_file.write(markdown_content)

    return json_file_name


def main() -> None:
    api_key = require_api_key()
    feed = fetch_feed()
    news_items = collect_news_items(feed)
    date_str = datetime.datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d")
    enrich_news_images(news_items, date_str)
    prompt = build_prompt(news_items)
    raw_text = call_gemini(api_key, prompt)
    ai_data = validate_ai_data(parse_model_json(raw_text), news_items)
    output_file = save_outputs(ai_data, news_items)
    print(f"Generated daily briefing: {output_file}")


if __name__ == "__main__":
    main()
