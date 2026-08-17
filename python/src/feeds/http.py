"""Shared HTTP client for public feeds. Never logs secrets."""

from __future__ import annotations

from typing import Any

import httpx

# SEC EDGAR requires a descriptive User-Agent with contact email or it 403s.
USER_AGENT = (
    "AlgoStrategySandbox/0.9 "
    "(+https://github.com/d7knight2/AlgoStrategySandbox; "
    "d7knight2@users.noreply.github.com)"
)


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
