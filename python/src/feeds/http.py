"""Shared HTTP client for public feeds. Never logs secrets."""

from __future__ import annotations

import re
from typing import Any

import httpx

# SEC rejects undeclared bots (403). Their sample is "Name email@domain".
# github noreply addresses are treated as undeclared and get 403.
USER_AGENT = "AlgoStrategySandbox paper-research@example.com"


def friendly_feed_error(raw: Any) -> str:
    """Short operator-safe error for Telegram. Never include URLs."""
    text = str(raw or "").strip()
    lower = text.lower()
    if "403" in text or "forbidden" in lower or "undeclared automated" in lower:
        return "SEC blocked automated access (403)"
    if "404" in text:
        return "not found (404)"
    if "timeout" in lower or "timed out" in lower:
        return "timed out"
    if "connect" in lower or "name or service not known" in lower:
        return "network error"
    cleaned = re.sub(r"https?://\S+", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :.-")
    return cleaned[:80] or "unavailable"


def get_json(url: str, *, timeout: float = 45.0, headers: dict[str, str] | None = None) -> Any:
    merged = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }
    if headers:
        merged.update(headers)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(url, headers=merged)
        r.raise_for_status()
        return r.json()
