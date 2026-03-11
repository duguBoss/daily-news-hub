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
MAX_IMAGES_PER_ARTICLE = 3
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
                "image_urls": [],
                "image_path": "",
                "image_paths": [],
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
  "articles": [
    {{
      "source_index": 1,
      "title_cn": "这条新闻的中文标题，18到32字",
      "summary_cn": "这条新闻的中文说明，45到90字，简短但包含关键信息"
    }}
  ],
  "editorial_notes": {{
    "timeline": "一句话描述今天国际新闻节奏，30到50字",
    "risk_watch": "一句话描述接下来值得关注的风险点，30到50字"
  }},
  "tags": ["国际新闻", "全球经济", "地缘局势", "科技商业", "能源供应"]
}}

进一步约束：
1. articles 必须覆盖下面素材中的每一条新闻，条数必须与素材条数完全一致。
2. articles 中每一项都必须包含 source_index、title_cn、summary_cn。
3. summary_cn 要简短，但必须包含关键事实、主体和最新进展，不要空泛。
4. cover_source_index 必须从 articles 的 source_index 中选择一个最适合作为封面的编号。
5. tags 固定输出 5 个。

以下是今日素材：
{news_text}
""".strip()


def build_fallback_ai_data(news_items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "title": "今日国际新闻综述",
        "seo_summary": "整理当日英文世界新闻中的主要国际动态，覆盖安全、经济、产业、能源与突发事件，并逐条输出简明中文说明。",
        "cover_source_index": next((item["index"] for item in news_items if item.get("image_url")), 1),
        "intro_paragraphs": [
            "今日国际新闻主要集中在地缘安全、全球市场、科技产业、能源链条及突发事件等方向，多条线索同步推进。",
            "以下内容按新闻条目逐条整理，统一转为中文，并保留每条新闻的原文链接与配图地址，便于直接使用。",
        ],
        "articles": [
            {
                "source_index": item["index"],
                "title_cn": item["title"],
                "summary_cn": item["summary"][:88] or item["title"],
            }
            for item in news_items
        ],
        "editorial_notes": {
            "timeline": "当天新闻节奏呈现多板块并行推进的状态，地缘、安全与市场信息交替升温。",
            "risk_watch": "后续可重点关注局势变化对能源运输、市场波动和企业经营预期的持续影响。",
        },
        "tags": ["国际新闻", "全球经济", "地缘局势", "科技商业", "能源供应"],
    }


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
    candidate = (result_json.get("candidates") or [{}])[0]
    finish_reason = candidate.get("finishReason", "")
    content = candidate.get("content") or {}
    parts = content.get("parts") or []

    if finish_reason in {"SAFETY", "RECITATION", "BLOCKLIST"}:
        raise RuntimeError(f"Gemini blocked the response with finishReason={finish_reason}: {result_json}")

    try:
        return parts[0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response shape: {result_json}") from exc


def parse_model_json(raw_text: str) -> dict[str, Any]:
    cleaned_text = raw_text.strip()
    code_block_match = re.search(r"```json\s*(\{.*?\})\s*```", cleaned_text, flags=re.IGNORECASE | re.DOTALL)
    if code_block_match:
        cleaned_text = code_block_match.group(1).strip()
    else:
        cleaned_text = re.sub(r"^```json\s*", "", cleaned_text, flags=re.IGNORECASE)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text).strip()

    decoder = json.JSONDecoder()
    try:
        parsed, _ = decoder.raw_decode(cleaned_text)
        return parsed
    except json.JSONDecodeError as exc:
        first_object_match = re.search(r"\{.*", cleaned_text, flags=re.DOTALL)
        if first_object_match:
            candidate = first_object_match.group(0)
            try:
                parsed, _ = decoder.raw_decode(candidate)
                return parsed
            except json.JSONDecodeError:
                pass
        raise RuntimeError(f"Model response is not valid JSON: {cleaned_text}") from exc


def build_article_translation_prompt(item: dict[str, Any]) -> str:
    lines = [
        "你是一个严格客观的国际新闻翻译与摘要助手。",
        "请把下面这条英文新闻转为简体中文，并输出合法 JSON。",
        "要求：",
        "1. 只输出 JSON，不要输出 markdown 或解释。",
        "2. 绝对客观，不添加观点，不夸张，不编造。",
        "3. 输出结构必须是：",
        '{"title_cn":"中文标题，18到32字","summary_cn":"中文说明，45到90字，简短但包含关键信息、主体和最新进展"}',
        f"英文标题：{item['title']}",
    ]
    if item.get("summary"):
        lines.append(f"英文摘要：{item['summary']}")
    if item.get("resolved_url") or item.get("google_news_url"):
        lines.append(f"原文链接：{item.get('resolved_url') or item.get('google_news_url')}")
    return "\n".join(lines)


def translate_news_items(api_key: str, news_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    translated_articles: list[dict[str, Any]] = []

    for item in news_items:
        prompt = build_article_translation_prompt(item)
        try:
            raw_text = call_gemini(api_key, prompt)
            translated = parse_model_json(raw_text)
            title_cn = normalize_whitespace(str(translated.get("title_cn", "")))
            summary_cn = normalize_whitespace(str(translated.get("summary_cn", "")))
            if not title_cn or not summary_cn:
                raise ValueError("Missing translated fields.")
        except Exception as exc:
            print(f"Skipping article {item['index']} due to translation failure: {exc}")
            continue

        translated_articles.append(
            {
                "source_index": item["index"],
                "title_cn": title_cn,
                "summary_cn": summary_cn,
                "image_urls": [],
                "image_caption": "",
                "image_source": "",
                "original_title": item["title"],
                "original_url": item["resolved_url"] or item["google_news_url"],
            }
        )

    return translated_articles


def build_ai_data_from_articles(
    translated_articles: list[dict[str, Any]], news_items: list[dict[str, Any]]
) -> dict[str, Any]:
    if not translated_articles:
        raise RuntimeError("No translated articles were produced.")

    cover_source_index = translated_articles[0]["source_index"]
    for item in news_items:
        if item["index"] in {article["source_index"] for article in translated_articles} and item["image_urls"]:
            cover_source_index = item["index"]
            break

    return {
        "title": "今日国际新闻速览",
        "seo_summary": f"精选 {len(translated_articles)} 条国际新闻，逐条转为中文，并附原文链接与仓库配图地址，便于直接分发和结构化读取。",
        "cover_source_index": cover_source_index,
        "intro_paragraphs": [
            f"本期内容共整理 {len(translated_articles)} 条国际新闻，覆盖安全、经济、产业、能源与突发事件等方向，统一转写为简体中文。",
            "每条新闻均尽量保留关键事实与最新进展，并在可抓取时附上已下载到 GitHub 的图片地址，便于直接用于前端或内容分发。",
        ],
        "articles": translated_articles,
        "editorial_notes": {
            "timeline": "当天国际新闻节奏整体偏密集，多个议题并行推进，安全与市场信息交替成为焦点。",
            "risk_watch": "后续可重点关注局势变化向市场、能源运输和企业经营预期的进一步传导。",
        },
        "tags": ["国际新闻", "全球经济", "地缘局势", "科技商业", "能源供应"],
    }


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

    max_index = len(news_items)
    raw_articles = ai_data.get("articles", [])
    if not isinstance(raw_articles, list) or len(raw_articles) < max_index:
        raise ValueError("articles must cover all source items.")

    articles = []
    seen_indexes = set()
    for raw_article in raw_articles:
        if not isinstance(raw_article, dict):
            continue
        try:
            source_index = int(raw_article.get("source_index"))
        except (TypeError, ValueError):
            continue
        if source_index in seen_indexes or not (1 <= source_index <= max_index):
            continue
        title_cn = normalize_whitespace(str(raw_article.get("title_cn", "")))
        summary_cn = normalize_whitespace(str(raw_article.get("summary_cn", "")))
        if not title_cn or not summary_cn:
            continue
        seen_indexes.add(source_index)
        articles.append(
            {
                "source_index": source_index,
                "title_cn": title_cn,
                "summary_cn": summary_cn,
                "image_urls": [],
                "image_caption": "",
                "image_source": "",
                "original_title": "",
                "original_url": "",
            }
        )

    if len(articles) < max_index:
        news_by_index = {item["index"]: item for item in news_items}
        for source_index in range(1, max_index + 1):
            if source_index in seen_indexes:
                continue
            item = news_by_index[source_index]
            articles.append(
                {
                    "source_index": source_index,
                    "title_cn": item["title"],
                    "summary_cn": item["summary"][:88] or item["title"],
                    "image_urls": [],
                    "image_caption": "",
                    "image_source": "",
                    "original_title": item["title"],
                    "original_url": item["resolved_url"] or item["google_news_url"],
                }
            )
    articles.sort(key=lambda article: article["source_index"])

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
        "articles": articles,
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


def choose_image_candidates(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
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
        normalized_candidate = {
            "src": src,
            "width": int(candidate.get("width") or 0),
            "height": int(candidate.get("height") or 0),
            "alt": normalize_whitespace(str(candidate.get("alt", ""))),
            "source": normalize_whitespace(str(candidate.get("source", ""))),
        }
        if score_image_candidate(normalized_candidate) >= 0:
            cleaned_candidates.append(normalized_candidate)

    cleaned_candidates.sort(key=score_image_candidate, reverse=True)
    return cleaned_candidates[:limit]


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

            best_candidates = choose_image_candidates(candidates, MAX_IMAGES_PER_ARTICLE)
            if not best_candidates:
                continue

            for image_index, candidate in enumerate(best_candidates, start=1):
                try:
                    image_path, image_url = download_image(
                        image_url=candidate["src"],
                        target_dir=target_dir,
                        file_stem=f"{item['index']:02d}-{image_index}-{slugify(item['title'])}",
                        referer=item["resolved_url"],
                    )
                except Exception:
                    continue

                item["image_paths"].append(image_path)
                item["image_urls"].append(image_url)
                if not item["image_url"]:
                    item["image_url"] = image_url
                    item["image_path"] = image_path
                    item["image_source"] = candidate["src"]
                    item["image_caption"] = item["title"]

        context.close()
        browser.close()


def attach_article_images(ai_data: dict[str, Any], news_items: list[dict[str, Any]]) -> str:
    news_by_index = {item["index"]: item for item in news_items}
    selected_cover = ""

    if ai_data["cover_source_index"]:
        cover_item = news_by_index.get(ai_data["cover_source_index"])
        if cover_item and cover_item["image_url"]:
            selected_cover = cover_item["image_url"]

    if not selected_cover:
        for item in news_items:
            if item["image_urls"]:
                selected_cover = item["image_urls"][0]
                break

    for article in ai_data["articles"]:
        item = news_by_index.get(article["source_index"])
        if not item:
            continue
        article["image_urls"] = item["image_urls"][:]
        article["image_caption"] = item["title"]
        article["image_source"] = item["resolved_url"] or item["google_news_url"]
        article["original_title"] = item["title"]
        article["original_url"] = item["resolved_url"] or item["google_news_url"]

    return selected_cover or FALLBACK_COVER_URL


def render_paragraph(text: str, extra_style: str = "") -> str:
    style = (
        "margin:0 0 18px 0;line-height:1.95;color:#1f2937;font-size:16px;"
        "letter-spacing:0.2px;text-align:justify;"
    )
    if extra_style:
        style += extra_style
    return f"<p style=\"{style}\">{html.escape(text)}</p>"


def render_article_images(article: dict[str, Any]) -> str:
    if not article["image_urls"]:
        return ""

    first_image_url = article["image_urls"][0]
    return (
        "<section style=\"margin:0 0 18px 0;\">"
        f"<img src=\"{html.escape(first_image_url)}\" style=\"width:100%;display:block;border-radius:2px;\">"
        "</section>"
    )


def render_html(
    ai_data: dict[str, Any],
    news_items: list[dict[str, Any]],
    cover_url: str,
    generated_at: str,
) -> str:
    title = html.escape(ai_data["title"])

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
            "</section>"
        ),
    ]

    for article in ai_data["articles"]:
        parts.append(
            "<section style=\"margin:0 0 38px 0;\">"
            "<div style=\"display:flex;align-items:center;margin:0 0 14px 0;\">"
            "<span style=\"display:inline-block;width:36px;height:2px;background:#111827;margin-right:12px;\"></span>"
            f"<h2 style=\"margin:0;font-size:22px;color:#111827;letter-spacing:0.4px;\">{html.escape(article['title_cn'])}</h2>"
            "</div>"
        )
        parts.append(render_article_images(article))
        parts.append(render_paragraph(article["summary_cn"]))
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
    ]

    for article in ai_data["articles"]:
        lines.extend([f"## {article['title_cn']}", ""])
        if article["image_urls"]:
            lines.append(f"配图：{article['image_urls'][0]}")
        lines.extend(["", article["summary_cn"], ""])

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
    cover_url = attach_article_images(ai_data, news_items)
    html_content = render_html(ai_data, news_items, cover_url, current_time)
    markdown_content = render_markdown(ai_data, news_items, cover_url, current_time)

    final_output = {
        "title": ai_data["title"],
        "seo_summary": ai_data["seo_summary"],
        "url": NEWS_SOURCE_URL,
        "cover": cover_url,
        "wechat_html": html_content,
        "intro_paragraphs": ai_data["intro_paragraphs"],
        "articles": ai_data["articles"],
        "editorial_notes": ai_data["editorial_notes"],
        "tags": ai_data["tags"],
        "generated_at": current_time,
        "is_daily_featured": True,
        "source_count": len(news_items),
        "image_count": sum(len(item["image_urls"]) for item in news_items),
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
    try:
        translated_articles = translate_news_items(api_key, news_items)
        ai_data = build_ai_data_from_articles(translated_articles, news_items)
    except Exception as exc:
        print(f"Falling back to local summary generation: {exc}")
        ai_data = validate_ai_data(build_fallback_ai_data(news_items), news_items)
    output_file = save_outputs(ai_data, news_items)
    print(f"Generated daily briefing: {output_file}")


if __name__ == "__main__":
    main()
