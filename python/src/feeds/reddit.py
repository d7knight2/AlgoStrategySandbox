"""Public Reddit JSON search for ticker + politician-trade chatter.

No OAuth / no paid key. Datacenter IPs often get 403 — fail soft.
Not used to size paper copies.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

from src.feeds.http import friendly_feed_error, get_json

log = logging.getLogger("trading_core.feeds.reddit")

SEARCH_URL = "https://www.reddit.com/search.json"
BULL = (
    "buy",
    "buying",
    "bought",
    "calls",
    "call",
    "long",
    "bull",
    "bullish",
    "moon",
    "rocket",
    "breakout",
    "accumulate",
    "undervalued",
)
BEAR = (
    "sell",
    "selling",
    "sold",
    "puts",
    "put",
    "short",
    "bear",
    "bearish",
    "crash",
    "dump",
    "overvalued",
    "bubble",
    "baghold",
)
GOV = (
    "pelosi",
    "congress",
    "senator",
    "house",
    "ptr",
    "stock act",
    "insider",
    "politician",
    "disclosure",
)


def _hits(text: str, words: tuple[str, ...]) -> int:
    hay = f" {text.lower()} "
    return sum(1 for w in words if f" {w} " in hay or hay.startswith(f"{w} "))


def score_posts(posts: list[dict[str, Any]]) -> dict[str, Any]:
    bull = bear = gov = 0
    score_sum = 0
    samples: list[str] = []
    for p in posts:
        title = str(p.get("title") or "")
        body = str(p.get("selftext") or "")[:280]
        blob = f"{title} {body}"
        ups = int(p.get("score") or 0)
        score_sum += max(ups, 0)
        b_hit = _hits(blob, BULL)
        s_hit = _hits(blob, BEAR)
        if b_hit > s_hit:
            bull += 1
        elif s_hit > b_hit:
            bear += 1
        if _hits(blob, GOV) or any(g in blob.lower() for g in ("pelosi", "stock act")):
            gov += 1
        if title and len(samples) < 3:
            samples.append(title[:140])
    net = bull - bear
    if not posts:
        label = "none"
    elif net >= 2:
        label = "bullish"
    elif net <= -2:
        label = "bearish"
    else:
        label = "mixed"
    return {
        "mentions": len(posts),
        "bullish": bull,
        "bearish": bear,
        "net": net,
        "label": label,
        "score_sum": score_sum,
        "gov_mentions": gov,
        "sample": samples,
    }


def _children(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data") or {}
    out: list[dict[str, Any]] = []
    for row in data.get("children") or []:
        if not isinstance(row, dict):
            continue
        inner = row.get("data") or {}
        if isinstance(inner, dict) and inner.get("title"):
            out.append(inner)
    return out


def fetch_reddit_sentiment(
    symbol: str,
    *,
    filer: str | None = None,
    sleep_s: float = 0.0,
) -> dict[str, Any]:
    """7-day Reddit search for $TICKER plus optional filer name."""
    sym = (symbol or "").upper().strip()
    if not sym:
        return {"ok": False, "symbol": symbol, "error": "empty symbol"}

    queries = [f"{sym} OR ${sym}"]
    if filer and filer.strip():
        queries.append(f'"{filer.strip()}" {sym}')

    posts: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for i, q in enumerate(queries):
        if i and sleep_s:
            time.sleep(sleep_s)
        params = {
            "q": q,
            "sort": "hot",
            "t": "week",
            "limit": "25",
            "type": "link",
            "raw_json": "1",
        }
        url = f"{SEARCH_URL}?{urlencode(params)}"
        try:
            payload = get_json(url, timeout=20.0)
        except Exception as exc:
            log.warning("reddit search failed symbol=%s error=%s", sym, exc)
            errors.append(friendly_feed_error(exc))
            continue
        for p in _children(payload):
            key = str(p.get("id") or p.get("title") or "")
            if key in seen:
                continue
            seen.add(key)
            posts.append(p)

    if not posts and errors:
        return {"ok": False, "symbol": sym, "error": errors[0]}

    scored = score_posts(posts)
    return {"ok": True, "symbol": sym, "error": errors[0] if errors else None, **scored}
