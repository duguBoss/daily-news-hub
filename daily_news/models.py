"""Multi-model API clients for AI content generation."""
from __future__ import annotations

import json
import os
from typing import Any

import requests

from daily_news.config import GEMINI_REQUEST_TIMEOUT, REQUEST_TIMEOUT


def is_quota_or_rate_limit_error(error_text: str) -> bool:
    """Check if error is quota or rate limit related."""
    text = error_text.lower()
    return (
        "resource_exhausted" in text
        or "quota exceeded" in text
        or "insufficient_quota" in text
        or "rate limit" in text
        or "too many requests" in text
        or "(429)" in text
    )


def _request_timeout(read_timeout: int) -> tuple[int, int]:
    """Return connection and read timeout tuple."""
    return (20, read_timeout)


def _response_excerpt(response: requests.Response, limit: int = 400) -> str:
    """Get excerpt from response for error messages."""
    try:
        body = response.text
    except Exception:
        body = ""
    return body[:limit].replace("\n", " ")


def call_gemini(api_key: str, prompt: str, model_name: str) -> str:
    """Call Gemini API with JSON response format."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.55,
            "topP": 0.9,
            "responseMimeType": "application/json",
        },
    }
    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=_request_timeout(GEMINI_REQUEST_TIMEOUT),
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"{model_name} request failed ({response.status_code}): "
            f"{_response_excerpt(response)}"
        )

    result = response.json()
    candidate = (result.get("candidates") or [{}])[0]
    content = candidate.get("content", {})
    parts = content.get("parts") or []
    if not parts:
        raise RuntimeError(f"{model_name} returned empty content.")
    return parts[0].get("text", "")


def call_minimax(api_key: str, prompt: str, model_name: str) -> str:
    """Call Minimax API using OpenAI-compatible format."""
    base_url = os.environ.get(
        "MINIMAX_OPENAI_BASE_URL", "https://api.minimax.chat/v1"
    )
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "stream": False,
    }
    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=_request_timeout(REQUEST_TIMEOUT),
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"MINIMAX request failed ({response.status_code}): "
            f"{_response_excerpt(response)}"
        )
    result = response.json()
    choices = result.get("choices", [])
    if not choices:
        raise RuntimeError("MINIMAX returned empty choices.")
    return choices[0].get("message", {}).get("content", "")


def call_openrouter(api_key: str, prompt: str, model_name: str) -> str:
    """Call OpenRouter API using OpenAI client."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    base_url = os.environ.get(
        "OPENROUTER_OPENAI_BASE_URL", "https://openrouter.ai/api/v1"
    )
    client = OpenAI(base_url=base_url, api_key=api_key)

    completion = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        temperature=0.55,
        top_p=0.9,
        extra_headers={
            "HTTP-Referer": os.environ.get(
                "OPENROUTER_SITE_URL", "https://github.com/duguBoss/daily-news-hub"
            ),
            "X-Title": os.environ.get("OPENROUTER_APP_NAME", "daily-news-hub"),
        },
    )
    if not completion.choices:
        raise RuntimeError("OpenRouter returned empty choices.")
    return completion.choices[0].message.content or ""


def extract_message_content(content: Any) -> str:
    """Extract text content from various response formats."""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and content:
        return "\n".join(str(item) for item in content if item)
    return str(content) if content else ""


def parse_model_json(text: str) -> dict[str, Any]:
    """Parse JSON from model response, handling markdown code blocks."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if text.startswith("json"):
        text = text[4:].strip()

    return json.loads(text)


def build_model_candidates(api_key: str) -> list[tuple[str, str, str, Any]]:
    """Build list of model candidates with their API callers.

    Returns list of (provider, model_name, api_key, caller_function).
    """
    candidates = []

    # Primary: Gemini models
    gemini_key = api_key
    if gemini_key:
        from daily_news.config import GEMINI_MODELS
        for model in GEMINI_MODELS:
            candidates.append(("gemini", model, gemini_key, call_gemini))

    # Fallback: Minimax
    minimax_key = os.environ.get("MINIMAX_API_KEY", "")
    minimax_model = os.environ.get("MINIMAX_MODEL", "MiniMax-Text-01")
    if minimax_key:
        candidates.append(("minimax", minimax_model, minimax_key, call_minimax))

    # Fallback: OpenRouter
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if openrouter_key:
        openrouter_models = [
            m.strip()
            for m in os.environ.get(
                "OPENROUTER_MODELS", "google/gemini-2.5-flash,google/gemini-2.5-pro"
            ).split(",")
            if m.strip()
        ]
        for model in openrouter_models:
            candidates.append(("openrouter", model, openrouter_key, call_openrouter))

    return candidates
