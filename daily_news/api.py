"""API client for Gemini and other external services."""
from __future__ import annotations

import json
import time
from typing import Any

import requests

from daily_news.config import GEMINI_MODEL_RETRIES, GEMINI_MODELS, REQUEST_TIMEOUT


def request_gemini(
    api_key: str,
    prompt: str,
    model_name: str,
    temperature: float = 0.7,
    max_tokens: int = 8192,
) -> str:
    """Make a request to Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}

    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }

    response = requests.post(
        url, headers=headers, params=params, json=payload, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("No candidates in Gemini response")

    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    if not parts:
        raise RuntimeError("No content parts in Gemini response")

    return parts[0].get("text", "")


def request_gemini_with_fallback(
    api_key: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 8192,
) -> str:
    """Request Gemini with model fallback."""
    last_error: Exception | None = None

    for model in GEMINI_MODELS:
        for attempt in range(GEMINI_MODEL_RETRIES):
            try:
                return request_gemini(api_key, prompt, model, temperature, max_tokens)
            except Exception as e:
                last_error = e
                print(f"Gemini request failed: model={model}, attempt={attempt + 1}, error={e}")
                time.sleep(1)

    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")


def parse_json_response(text: str) -> dict[str, Any]:
    """Parse JSON from API response, handling markdown code blocks."""
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
