from __future__ import annotations

import datetime
import hashlib
import html
import json
import mimetypes
import os
import re
import shutil
import time
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
GEMINI_MODELS = [
    model.strip()
    for model in os.environ.get(
        "GEMINI_MODELS",
        (
            "gemini-3.1-pro-preview,"
            "gemini-3-flash-preview,"
            "gemini-3.1-flash-lite-preview,"
            "gemini-2.5-flash,"
            "gemini-2.5-flash-lite,"
            "gemini-2.5-pro"
        ),
    ).split(",")
    if model.strip()
]
GEMINI_MODEL_RETRIES = max(1, int(os.environ.get("GEMINI_MODEL_RETRIES", "2")))
REQUEST_TIMEOUT = 30
PLAYWRIGHT_TIMEOUT_MS = 25000
MAX_NEWS_ITEMS = 36
MIN_NEWS_ITEMS = 8
MAX_IMAGE_DISCOVERY_ITEMS = 12
MAX_IMAGES_PER_ARTICLE = 3
MIN_REQUIRED_ARTICLE_IMAGES = 3
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

CHINA_RELATED_PATTERNS =[
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
    items: list[dict[str, Any]] =[]

    for entry in feed.entries:
        title = normalize_whitespace(entry.get("title", ""))
        summary = normalize_whitespace(re.sub(r"<[^>]+>", " ", entry.get("summary", "")))
        google_news_url = entry.get("link", "")
        combined = " ".join(part for part in[title, summary] if part)

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
                "image_urls":[],
                "image_path": "",
                "image_paths":[],
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


def build_fallback_ai_data(news_items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "title": "突发！多国重磅消息流出，国际局势突变",
        "seo_summary": "重磅进展：深入追踪当日核心突发动态，一文看懂地缘冲突、宏观经济与前沿异动。",
        "cover_source_index": next((item["index"] for item in news_items if item.get("image_url")), 1),
        "intro_paragraphs":[
            "今日国际新闻主要集中在地缘安全、全球市场、科技产业、能源链条及突发事件等方向，多条线索同步推进。",
            "以下内容按新闻条目逐条整理，统一转为中文，并保留每条新闻的原文链接与配图地址，便于直接使用。",
        ],
        "articles":[
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
        "tags":["国际新闻", "全球经济", "地缘局势", "科技商业", "能源供应"],
    }


def is_quota_or_rate_limit_error(error_text: str) -> bool:
    text = (error_text or "").lower()
    return (
        "resource_exhausted" in text
        or "quota exceeded" in text
        or "insufficient_quota" in text
        or "rate limit" in text
        or "(429)" in text
        or " 429" in text
    )


def request_gemini(api_key: str, prompt: str, model_name: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent?key={api_key}"
    )
    payload = {
        "contents":[{"parts":[{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "topP": 0.9,
            "responseMimeType": "application/json",
        },
        "safetySettings":[
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
            f"{model_name} request failed ({response.status_code}): {response.text}"
        )

    result_json = response.json()
    candidate = (result_json.get("candidates") or [{}])[0]
    finish_reason = candidate.get("finishReason", "")
    content = candidate.get("content") or {}
    parts = content.get("parts") or[]

    if finish_reason in {"SAFETY", "RECITATION", "BLOCKLIST"}:
        raise RuntimeError(f"Gemini blocked the response with finishReason={finish_reason}: {result_json}")

    try:
        return parts[0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"{model_name} returned unexpected response shape: {result_json}") from exc


def call_gemini(api_key: str, prompt: str) -> str:
    last_error = None
    for model_name in GEMINI_MODELS:
        for attempt in range(1, GEMINI_MODEL_RETRIES + 1):
            try:
                return request_gemini(api_key=api_key, prompt=prompt, model_name=model_name)
            except Exception as exc:
                last_error = exc
                print(
                    f"Gemini attempt {attempt}/{GEMINI_MODEL_RETRIES} with {model_name} failed: {exc}"
                )
                if attempt < GEMINI_MODEL_RETRIES:
                    time.sleep(1.2 * attempt)
                if is_quota_or_rate_limit_error(str(exc)):
                    continue

    raise RuntimeError(
        f"Gemini failed on all fallback models after retries. Last error: {last_error}"
    )


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
    lines =[
        "你是一个严格客观的国际新闻翻译与摘要助手。",
        "请把下面这条英文新闻转为简体中文，并输出合法 JSON。",
        "要求：",
        "1. 只输出 JSON，不要输出 markdown 或解释。",
        "2. 绝对客观，不添加观点，不夸张，不编造。",
        "3. 输出结构必须是：",
        '{"title_cn":"包含核心实体名称的完整中文标题，适合SEO，18到32字","summary_cn":"包含核心事实、具体事件主体和最新进展的内容摘要，适合SEO抓取，45到90字"}',
        f"英文标题：{item['title']}",
    ]
    if item.get("summary"):
        lines.append(f"英文摘要：{item['summary']}")
    if item.get("resolved_url") or item.get("google_news_url"):
        lines.append(f"原文链接：{item.get('resolved_url') or item.get('google_news_url')}")
    return "\n".join(lines)


def translate_news_items(api_key: str, news_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    translated_articles: list[dict[str, Any]] =[]

    for item in news_items:
        prompt = build_article_translation_prompt(item)
        fallback_title = item["title"]
        fallback_summary = item["summary"][:120] or item["title"]
        try:
            raw_text = call_gemini(api_key, prompt)
            translated = parse_model_json(raw_text)
            title_cn = normalize_whitespace(str(translated.get("title_cn", "")))
            summary_cn = normalize_whitespace(str(translated.get("summary_cn", "")))
            if not title_cn or not summary_cn:
                raise ValueError("Missing translated fields.")
        except Exception as exc:
            print(f"Translation failed for article {item['index']}, using fallback text: {exc}")
            title_cn = fallback_title
            summary_cn = fallback_summary

        translated_articles.append(
            {
                "source_index": item["index"],
                "title_cn": title_cn,
                "summary_cn": summary_cn,
                "image_urls":[],
                "image_caption": "",
                "image_source": "",
                "original_title": item["title"],
                "original_url": item["resolved_url"] or item["google_news_url"],
            }
        )

    return translated_articles


def generate_metadata(api_key: str, translated_articles: list[dict[str, Any]]) -> dict[str, Any]:
    articles_text = "\n".join([f"- {a['title_cn']}: {a['summary_cn']}" for a in translated_articles])
    prompt = f"""
你是一个深谙新媒体爆款逻辑的高级国际新闻主编。请根据今日的新闻内容，生成极具吸引力的推文元数据。

要求：
1. 语气要带有“突发”、“重磅”等实时新闻的紧迫感（即适度的“标题党”），必须基于事实制造悬念或强调其巨大影响。
2. title：生成一个极具冲击力的主标题（必须是完整的一句话，严格控制在 32 字以内）。【极其重要】必须提取今天最震撼的核心事件（如“突发！XXX在某地遇袭”）。绝对禁止包含“福布斯”、“路透社”等媒体名字。绝对禁止使用“XXX等重磅要闻”、“新闻大盘点”等拼凑废话。
3. seo_summary：生成一段极度凝练且极具吸引力的新闻摘要（必须是完整的句子，严格控制在 50 字以内）。直击最重磅的事件痛点，制造点击悬念，适合SEO抓取。绝不要凑字数。
4. timeline：一句话概括今天新闻的整体节奏或主要脉络（30-50字）。
5. risk_watch：一句话提示从今天新闻中观察到的值得重点关注的演变趋势或风险点（30-50字）。
6. 仅返回合法的 JSON 格式，禁止输出 markdown 代码块。

输出 JSON 结构：
{{
  "title": "...",
  "seo_summary": "...",
  "timeline": "...",
  "risk_watch": "..."
}}

今日新闻素材：
{articles_text}
"""
    try:
        raw_text = call_gemini(api_key, prompt)
        return parse_model_json(raw_text)
    except Exception as exc:
        print(f"Failed to generate metadata via AI (Likely Rate Limit), using smart fallback. Error: {exc}")
        return {}


def build_ai_data_from_articles(
    api_key: str,
    translated_articles: list[dict[str, Any]], 
    news_items: list[dict[str, Any]]
) -> dict[str, Any]:
    if not translated_articles:
        raise RuntimeError("No translated articles were produced.")

    # 加入 3 秒休眠，防止上文连续的十几条翻译调用耗尽 API 并发限制
    time.sleep(3)

    metadata = generate_metadata(api_key, translated_articles)

    # ---------------------------------------------------------
    # 彻底告别残缺和无意义媒体名字的智能兜底 (Smart Fallback)
    # ---------------------------------------------------------
    # 提取第一条新闻，利用正则干掉形如“福布斯：”、“路透社透露：”等前缀
    first_title_raw = translated_articles[0]["title_cn"]
    clean_first_title = re.sub(r"^[^：:]+[：:]\s*", "", first_title_raw).strip()
    
    # 组成一句话完整标题
    smart_title = f"突发重磅！{clean_first_title}"
    
    # 防溢出：如果超出32字，安全截断并补上省略号，保留悬念
    if len(smart_title) > 32:
        smart_title = smart_title[:31] + "…"

    # 摘要逻辑同理
    first_summary_raw = translated_articles[0]['summary_cn']
    smart_summary = f"重磅进展：{first_summary_raw}"
    if len(smart_summary) > 50:
        smart_summary = smart_summary[:48] + "..."

    title = metadata.get("title") or smart_title
    seo_summary = metadata.get("seo_summary") or smart_summary
    timeline = metadata.get("timeline") or "当天国际新闻节奏密集，多板块地缘与市场信息交替成为核心焦点。"
    risk_watch = metadata.get("risk_watch") or "请高度警惕重大事件演变对全球供应链、能源定价及市场预期的传导。"

    # 最后一道强制保险，保证 AI 生成的也严格不超字数
    if len(title) > 32:
        title = title[:31] + "…"
    if len(seo_summary) > 50:
        seo_summary = seo_summary[:48] + "..."

    cover_source_index = translated_articles[0]["source_index"]
    for item in news_items:
        if item["index"] in {article["source_index"] for article in translated_articles} and item["image_urls"]:
            cover_source_index = item["index"]
            break

    return {
        "title": title,
        "seo_summary": seo_summary,
        "cover_source_index": cover_source_index,
        "intro_paragraphs":[
            f"本期内容共整理 {len(translated_articles)} 条国际新闻，覆盖安全、经济、产业、能源与突发事件等方向，统一转写为简体中文。",
            "每条新闻均尽量保留关键事实与最新进展，并在可抓取时附上已下载到 GitHub 的图片地址，便于直接用于前端或内容分发。",
        ],
        "articles": translated_articles,
        "editorial_notes": {
            "timeline": timeline,
            "risk_watch": risk_watch,
        },
        "tags":["国际新闻", "全球经济", "地缘局势", "科技商业", "突发要闻"],
    }


def ensure_list_of_strings(value: Any, field_name: str, min_items: int = 1) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list.")

    cleaned =[normalize_whitespace(str(item)) for item in value if str(item).strip()]
    if len(cleaned) < min_items:
        raise ValueError(f"{field_name} requires at least {min_items} items.")
    return cleaned


def normalize_source_indexes(value: Any, max_index: int) -> list[int]:
    if not isinstance(value, list):
        return[]

    indexes: list[int] =[]
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

    title = normalize_whitespace(str(ai_data.get("title", "突发！多国重磅消息流出，国际局势突变")))
    if len(title) > 32:
        title = title[:31] + "…"

    seo_summary = normalize_whitespace(
        str(
            ai_data.get(
                "seo_summary",
                "重磅进展：深入追踪当日核心突发动态，一文看懂地缘冲突、宏观经济与科技巨头最新异动。",
            )
        )
    )
    if len(seo_summary) > 50:
        seo_summary = seo_summary[:48] + "..."

    intro_paragraphs = ensure_list_of_strings(
        ai_data.get("intro_paragraphs",[]), "intro_paragraphs", min_items=2
    )[:2]
    tags = ensure_list_of_strings(ai_data.get("tags",[]), "tags", min_items=5)[:5]

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
    raw_articles = ai_data.get("articles",[])
    if not isinstance(raw_articles, list) or len(raw_articles) < max_index:
        raise ValueError("articles must cover all source items.")

    articles =[]
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
                "image_urls":[],
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
                    "image_urls":[],
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


def is_valid_image_url(url: str) -> bool:
    value = normalize_whitespace(str(url))
    if not value:
        return False
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    path = parsed.path.lower()
    return any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"))


def sanitize_image_url_list(urls: list[Any]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in urls:
        value = normalize_whitespace(str(raw))
        if not value or value in seen:
            continue
        if not is_valid_image_url(value):
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def normalize_news_item_images(item: dict[str, Any]) -> None:
    valid_urls = sanitize_image_url_list(item.get("image_urls", []))
    valid_paths = [normalize_whitespace(str(path)) for path in item.get("image_paths", []) if str(path).strip()]

    item["image_urls"] = valid_urls
    item["image_paths"] = valid_paths[: len(valid_urls)]
    if valid_urls:
        item["image_url"] = valid_urls[0]
        item["image_path"] = item["image_paths"][0] if item["image_paths"] else ""
    else:
        item["image_url"] = ""
        item["image_path"] = ""
        item["image_source"] = ""
        item["image_caption"] = ""


def count_news_items_with_images(news_items: list[dict[str, Any]]) -> int:
    count = 0
    for item in news_items:
        normalize_news_item_images(item)
        if item.get("image_urls"):
            count += 1
    return count


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
    if any(token in src.lower() for token in["logo", "icon", "sprite", "avatar"]):
        score -= 250
    if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
        score -= 300
    return score


def choose_best_image_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    cleaned_candidates =[]
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
    cleaned_candidates =[]
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
    for ext in[".jpg", ".jpeg", ".png", ".webp", ".gif"]:
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


def enrich_news_images(
    news_items: list[dict[str, Any]],
    date_str: str,
    max_items: int | None = None,
    only_missing: bool = True,
) -> None:
    if not PLAYWRIGHT_AVAILABLE:
        print("Playwright is not installed. Skipping article image discovery.")
        return

    target_dir = ASSET_ROOT / date_str
    candidate_items = [
        item
        for item in news_items
        if item.get("google_news_url") and (not only_missing or not item.get("image_urls"))
    ]
    if max_items is not None and max_items > 0:
        candidate_items = candidate_items[:max_items]

    if not candidate_items:
        return

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_navigation_timeout(PLAYWRIGHT_TIMEOUT_MS)

        for item in candidate_items:
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
                        const urls =[];
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
            normalize_news_item_images(item)

        context.close()
        browser.close()


def ensure_minimum_article_images(news_items: list[dict[str, Any]], date_str: str) -> None:
    current_with_images = count_news_items_with_images(news_items)
    if current_with_images >= MIN_REQUIRED_ARTICLE_IMAGES:
        return

    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright is required to guarantee image availability, but it is not installed."
        )

    discovery_limits = [
        max(MAX_IMAGE_DISCOVERY_ITEMS, MIN_REQUIRED_ARTICLE_IMAGES * 4),
        min(len(news_items), max(MAX_IMAGE_DISCOVERY_ITEMS * 2, MIN_REQUIRED_ARTICLE_IMAGES * 8)),
        len(news_items),
    ]
    for limit in discovery_limits:
        if current_with_images >= MIN_REQUIRED_ARTICLE_IMAGES:
            break
        enrich_news_images(news_items, date_str=date_str, max_items=limit, only_missing=True)
        current_with_images = count_news_items_with_images(news_items)
        print(
            f"Image coverage check: {current_with_images} articles with valid images "
            f"(required {MIN_REQUIRED_ARTICLE_IMAGES}, scanned up to {limit})."
        )

    if current_with_images < MIN_REQUIRED_ARTICLE_IMAGES:
        raise RuntimeError(
            f"Not enough articles with valid images after retries: "
            f"{current_with_images}/{MIN_REQUIRED_ARTICLE_IMAGES}."
        )


def attach_article_images(ai_data: dict[str, Any], news_items: list[dict[str, Any]]) -> str:
    news_by_index = {item["index"]: item for item in news_items}
    selected_cover = ""

    if ai_data["cover_source_index"]:
        cover_item = news_by_index.get(ai_data["cover_source_index"])
        if cover_item:
            normalize_news_item_images(cover_item)
            if cover_item["image_url"]:
                selected_cover = cover_item["image_url"]

    if not selected_cover:
        for item in news_items:
            normalize_news_item_images(item)
            if item["image_urls"]:
                selected_cover = item["image_urls"][0]
                break

    for article in ai_data["articles"]:
        item = news_by_index.get(article["source_index"])
        if not item:
            continue
        normalize_news_item_images(item)
        article["image_urls"] = item["image_urls"][:]
        article["image_caption"] = item["title"]
        article["image_source"] = item["resolved_url"] or item["google_news_url"]
        article["original_title"] = item["title"]
        article["original_url"] = item["resolved_url"] or item["google_news_url"]

    return selected_cover or FALLBACK_COVER_URL


def render_paragraph(text: str, extra_style: str = "") -> str:
    style = (
        "margin:0 0 6px 0;line-height:1.8;color:#334155;font-size:16px;"
        "letter-spacing:0.5px;text-align:justify;"
    )
    if extra_style:
        style += extra_style
    return f"<p style=\"{style}\">{html.escape(text)}</p>"


def render_article_images(article: dict[str, Any]) -> str:
    if not article["image_urls"]:
        return ""

    first_image_url = article["image_urls"][0]
    return (
        "<section style=\"margin:0 0 10px 0;\">"
        f"<img src=\"{html.escape(first_image_url)}\" style=\"width:100%;display:block;border-radius:4px;border:1px solid #f1f5f9;\">"
        "</section>"
    )


def render_html(
    ai_data: dict[str, Any],
    news_items: list[dict[str, Any]],
    cover_url: str,
    generated_at: str,
) -> str:
    title = html.escape(ai_data["title"])

    parts =[
        "<section style=\"margin:0;padding:0;background:#ffffff;\">",
        f"<img src=\"{TOP_BANNER_URL}\" style=\"width:100%;display:block;\">",
        (
            "<section style=\"max-width:760px;margin:0 auto;padding:2px;\">"
        ),
        (
            "<section style=\"margin:12px 0 16px 0;padding:2px 2px 8px 2px;border-bottom:2px solid #1e293b;\">"
            "<div style=\"font-size:12px;letter-spacing:2px;color:#b59f7b;text-transform:uppercase;margin-bottom:4px;font-weight:600;\">Global Briefing</div>"
            f"<h1 style=\"margin:0;font-size:26px;line-height:1.4;color:#0f172a;font-weight:bold;letter-spacing:0.5px;\">{title}</h1>"
            "</section>"
        ),
    ]

    for article in ai_data["articles"]:
        parts.append(
            "<section style=\"margin:0 0 18px 0;padding:0 2px 14px 2px;border-bottom:1px solid #f1f5f9;\">"
            f"<h2 style=\"margin:0 0 12px 0;padding-left:10px;border-left:4px solid #b59f7b;font-size:20px;line-height:1.5;color:#1e293b;letter-spacing:0.5px;\">{html.escape(article['title_cn'])}</h2>"
        )
        parts.append(render_article_images(article))
        parts.append(render_paragraph(article["summary_cn"]))
        parts.append(
            "<div style=\"margin-top:8px;text-align:right;\">"
            "<span style=\"display:inline-block;font-size:11px;letter-spacing:1px;color:#94a3b8;text-transform:uppercase;border-bottom:1px solid #f1f5f9;padding-bottom:2px;\">Global Watch</span>"
            "</div>"
            "</section>"
        )

    parts.append(
        "<section style=\"margin:16px 2px;padding:14px;background:#0f172a;border-top:3px solid #b59f7b;border-radius:2px;\">"
        "<div style=\"font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#b59f7b;margin-bottom:8px;font-weight:600;\">Risk Watch</div>"
        f"<p style=\"margin:0 0 6px 0;font-size:15px;line-height:1.8;color:#e2e8f0;text-align:justify;\"><strong>趋势：</strong>{html.escape(ai_data['editorial_notes']['timeline'])}</p>"
        f"<p style=\"margin:0;font-size:15px;line-height:1.8;color:#e2e8f0;text-align:justify;\"><strong>关注：</strong>{html.escape(ai_data['editorial_notes']['risk_watch'])}</p>"
        "</section>"
    )

    parts.append(
        "<section style=\"margin:12px 2px 0 2px;padding-top:12px;border-top:1px dashed #cbd5e1;\">"
        "<div style=\"font-size:12px;letter-spacing:1px;color:#64748b;text-transform:uppercase;margin-bottom:8px;\">Keywords</div>"
    )
    for tag in ai_data["tags"]:
        parts.append(
            f"<span style=\"display:inline-block;margin:0 8px 8px 0;padding:4px 10px;border:1px solid #e2e8f0;border-radius:2px;background:#f8fafc;color:#475569;font-size:12px;letter-spacing:0.5px;\">{html.escape(tag)}</span>"
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

    lines.extend([
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
    peitu_urls: list[str] = []
    seen_peitu: set[str] = set()
    for article in ai_data["articles"]:
        article_urls = sanitize_image_url_list(article.get("image_urls", []))
        if not article_urls:
            continue
        first_url = article_urls[0]
        if first_url in seen_peitu:
            continue
        seen_peitu.add(first_url)
        peitu_urls.append(first_url)

    if len(peitu_urls) < MIN_REQUIRED_ARTICLE_IMAGES:
        raise RuntimeError(
            f"peitu_url must include at least {MIN_REQUIRED_ARTICLE_IMAGES} valid image URLs, "
            f"but got {len(peitu_urls)}."
        )

    final_output = {
        "title": ai_data["title"],
        "seo_summary": ai_data["seo_summary"],
        "url": NEWS_SOURCE_URL,
        "cover": cover_url,
        "peitu_url": peitu_urls,
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


def clean_old_files(days_to_keep: int = 1) -> None:
    """Clean old files, keeping only the most recent days. Default: 1 day (today only)."""
    cutoff_date = datetime.datetime.now(SHANGHAI_TZ) - datetime.timedelta(days=days_to_keep)

    for file_path in Path(".").glob("Daily_News_*.md"):
        file_date_str = file_path.stem.replace("Daily_News_", "")
        try:
            file_date = datetime.datetime.strptime(file_date_str, "%Y-%m-%d").replace(tzinfo=SHANGHAI_TZ)
            if file_date < cutoff_date:
                file_path.unlink()
                print(f"Deleted old file: {file_path}")
        except ValueError:
            continue

    for file_path in Path(".").glob("Daily_News_*.json"):
        file_date_str = file_path.stem.replace("Daily_News_", "")
        try:
            file_date = datetime.datetime.strptime(file_date_str, "%Y-%m-%d").replace(tzinfo=SHANGHAI_TZ)
            if file_date < cutoff_date:
                file_path.unlink()
                print(f"Deleted old file: {file_path}")
        except ValueError:
            continue

    assets_dir = Path("assets") / "generated"
    if assets_dir.exists():
        for date_dir in assets_dir.iterdir():
            if date_dir.is_dir():
                try:
                    dir_date = datetime.datetime.strptime(date_dir.name, "%Y-%m-%d").replace(tzinfo=SHANGHAI_TZ)
                    if dir_date < cutoff_date:
                        shutil.rmtree(date_dir)
                        print(f"Deleted old directory: {date_dir}")
                except ValueError:
                    continue


def main() -> None:
    clean_old_files()
    api_key = require_api_key()
    feed = fetch_feed()
    news_items = collect_news_items(feed)
    date_str = datetime.datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d")
    ensure_minimum_article_images(news_items, date_str)
    try:
        translated_articles = translate_news_items(api_key, news_items)
        ai_data = build_ai_data_from_articles(api_key, translated_articles, news_items)
    except Exception as exc:
        print(f"Falling back to local summary generation: {exc}")
        ai_data = validate_ai_data(build_fallback_ai_data(news_items), news_items)
    output_file = save_outputs(ai_data, news_items)
    print(f"Generated daily briefing: {output_file}")


if __name__ == "__main__":
    main()
