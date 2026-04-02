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

# Gemini configuration - matching daily-nasa-hub
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
GEMINI_REQUEST_TIMEOUT = 60
REQUEST_TIMEOUT = 30
PLAYWRIGHT_TIMEOUT_MS = 25000

# Retry configuration
MAX_TITLE_RETRIES = max(1, int(os.environ.get("MAX_TITLE_RETRIES", "3")))
MAX_CARD_RETRIES = max(1, int(os.environ.get("MAX_CARD_RETRIES", "3")))

# Content limits
MAX_NEWS_ITEMS = 36
MIN_NEWS_ITEMS = 8
MAX_IMAGE_DISCOVERY_ITEMS = 12
MAX_IMAGES_PER_ARTICLE = 3
MIN_REQUIRED_ARTICLE_IMAGES = 3
MIN_IMAGE_WIDTH = 360
MIN_IMAGE_HEIGHT = 200

# Image processing
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
JPEG_QUALITY = 85

# Timezone
SHANGHAI_TZ = pytz.timezone("Asia/Shanghai")

# Asset paths
ASSET_ROOT = Path("assets")

# Banner URLs
FALLBACK_COVER_URL = ""
TOP_BANNER_URL = ""
BOTTOM_BANNER_URL = ""

# China-related patterns for filtering
CHINA_RELATED_PATTERNS = [
    "china", "chinese", "beijing", "shanghai", "guangzhou", "shenzhen",
    "hong kong", "taiwan", "taipei", "xinjiang", "tibet", "macau", "macao",
    "people's republic of china", "prc", "ccp", "communist party of china",
]