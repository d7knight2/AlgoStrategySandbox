"""US STOCK Act periodic transaction reports (House + Senate).

Public JSON aggregates of official efdsearch.senate.gov / House Clerk filings.
Disclosures are delayed (often up to 45 days). Paper research only.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from src.feeds.http import get_json

log = logging.getLogger("trading_core.feeds.congress")

SENATE_URLS = [
    "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json",
    "https://cdn.jsdelivr.net/gh/timothycarambat/senate-stock-watcher-data@master/aggregate/all_transactions.json",
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json",
]
HOUSE_URLS = [
    "https://raw.githubusercontent.com/TattooedHead/house-stock-watcher-data/main/data/all_transactions.json",
    "https://cdn.jsdelivr.net/gh/TattooedHead/house-stock-watcher-data@main/data/all_transactions.json",
    "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json",
]

_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")
_SKIP = {"", "--", "N/A", "NA", "NONE", "VARIOUS", "CALL", "PUT"}


def _first_json(urls: list[str]) -> list[dict[str, Any]]:
    last_err: Exception | None = None
    for url in urls:
        try:
            data = get_json(url)
            if isinstance(data, list):
                return data
            last_err = ValueError(f"unexpected JSON type from {url}")
        except Exception as exc:
            last_err = exc
            log.warning("congress feed failed url=%s error=%s", url, exc)
    raise RuntimeError(f"all congress URLs failed: {last_err}")


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def normalize_ticker(raw: str | None) -> str | None:
    if not raw:
        return None
    sym = str(raw).strip().upper().replace("$", "")
    if " " in sym:
        return None
    if sym in _SKIP or not _TICKER_RE.match(sym):
        return None
    return sym


def normalize_side(raw: str | None) -> str | None:
    text = (raw or "").strip().lower()
    if not text:
        return None
    if "purchase" in text or text == "buy" or "buy" in text:
        if "sell" in text:
            return None
        return "buy"
    if "sale" in text or "sell" in text:
        return "sell"
    return None


def _filer_name(row: dict[str, Any]) -> str:
    for key in ("senator", "representative", "name", "full_name", "member"):
        val = row.get(key)
        if val:
            return str(val).strip()
    return ""


def _matches_watchlist(name: str, watchlist: list[str]) -> str | None:
    hay = name.lower()
    for needle in watchlist:
        n = needle.strip().lower()
        if n and n in hay:
            return needle.strip()
    return None


def event_key(row: dict[str, Any], *, chamber: str, symbol: str, side: str) -> str:
    filer = _filer_name(row)
    disclosed = str(row.get("disclosure_date") or "")
    traded = str(row.get("transaction_date") or "")
    amount = str(row.get("amount") or "")
    ttype = str(row.get("type") or "")
    return "|".join([chamber, filer, symbol, side, disclosed, traded, ttype, amount])[:250]


def fetch_watchlist_trades(
    watchlist: list[str],
    *,
    lookback_days: int = 45,
) -> list[dict[str, Any]]:
    """Return recent STOCK Act rows for names on the watchlist."""
    cutoff = datetime.utcnow() - timedelta(days=max(1, lookback_days))
    names = [w.strip() for w in watchlist if w.strip()]
    out: list[dict[str, Any]] = []

    for chamber, urls in (("senate", SENATE_URLS), ("house", HOUSE_URLS)):
        try:
            rows = _first_json(urls)
        except Exception as exc:
            log.warning("skip %s feed: %s", chamber, exc)
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            filer = _filer_name(row)
            matched = _matches_watchlist(filer, names)
            if not matched:
                continue
            symbol = normalize_ticker(row.get("ticker"))
            side = normalize_side(row.get("type"))
            if not symbol or not side:
                continue
            disclosed = _parse_date(row.get("disclosure_date"))
            if disclosed is None or disclosed < cutoff:
                continue
            out.append(
                {
                    "source": f"stock_act_{chamber}",
                    "chamber": chamber,
                    "filer": filer,
                    "watchlist_match": matched,
                    "symbol": symbol,
                    "side": side,
                    "amount": str(row.get("amount") or ""),
                    "asset": str(row.get("asset_description") or "")[:120],
                    "disclosure_date": str(row.get("disclosure_date") or ""),
                    "transaction_date": str(row.get("transaction_date") or ""),
                    "ptr_link": str(row.get("ptr_link") or row.get("link") or ""),
                    "event_key": event_key(row, chamber=chamber, symbol=symbol, side=side),
                }
            )

    out.sort(key=lambda r: r.get("disclosure_date") or "", reverse=True)
    return out
