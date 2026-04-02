"""Configuration constants for daily news hub."""
from __future__ import annotations

import os
from pathlib import Path

import pytz

RSS_URL = (
    "https://news.google.com/rss/headlines/section/topic/WORLD"
    "?hl=en-US&gl=US&ceid=US:en"
)
NEWS_SOURCE_URL = (
    "https://news.google.com/topics/"
    "CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx1YlY4U0JXVnVMVWRDR2dKRFFTZ0FQAQ"
    "?hl=en-US&gl=US&ceid=US%3Aen"
)

DEFAULT_REPOSITORY = "duguBoss/daily-news-hub"
DEFAULT_BRANCH = "main"

GEMINI_MODELS = [
    m.strip()
    for m in os.environ.get(
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
    if m.strip()
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
    "3hAJnwuyZuicicicZkgJBUCCaricdibomDBrTzXgUR7FJnf11qGIo8nmKt6RxibXrb5s4RFb9UZ9UOHQy7fqQyI377Licw/"
    "0?wx_fmt=gif"
)
BOTTOM_BANNER_URL = (
    "https://mmbiz.qpic.cn/mmbiz_gif/"
    "3hAJnwuyZuicicicZkgJBUCCaricdibomDBrTzk57DCmhVC16o9ILH0Tn1YPEiarfLRRQSVFN2mJdeYibGnBPialPIzvojw/"
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
    r"\btaiwan\b",
    r"\btaipei\b",
