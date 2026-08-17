"""Public sentiment / risk-off gauges (no API key)."""

from __future__ import annotations

import logging
from typing import Any

from src.feeds.http import get_json

log = logging.getLogger("trading_core.feeds.sentiment")

FNG_URL = "https://api.alternative.me/fng/?limit=1&format=json"


def fetch_fear_greed() -> dict[str, Any]:
    """CNN-style Fear & Greed clone from alternative.me (crypto-heavy but public)."""
    try:
        data = get_json(FNG_URL, timeout=20.0)
        rows = data.get("data") if isinstance(data, dict) else None
        if not rows:
            return {"ok": False, "error": "empty fear-greed payload"}
        row = rows[0]
        value = int(row.get("value"))
        label = str(row.get("value_classification") or "")
        return {
            "ok": True,
            "value": value,
            "label": label,
            "as_of": row.get("timestamp"),
        }
    except Exception as exc:
        log.warning("fear-greed fetch failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300]}
