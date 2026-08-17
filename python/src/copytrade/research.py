"""Enrich STOCK Act rows with Reddit chatter, 7d/30d stats, and leverage flags."""

from __future__ import annotations

import logging
import time
from collections import Counter
from typing import Any

from src.copytrade.stats import parse_event_date, price_stats
from src.feeds.http import friendly_feed_error
from src.feeds.leverage import classify_instrument
from src.feeds.reddit import fetch_reddit_sentiment

log = logging.getLogger("trading_core.copytrade.research")

MAX_SYMBOLS = 8
REDDIT_PAUSE_S = 0.7


def window_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    buys = [t for t in trades if (t.get("side") or "").lower() == "buy"]
    sells = [t for t in trades if (t.get("side") or "").lower() == "sell"]
    buy_c = Counter(str(t.get("symbol") or "").upper() for t in buys if t.get("symbol"))
    sell_c = Counter(str(t.get("symbol") or "").upper() for t in sells if t.get("symbol"))
    filers = sorted({str(t.get("watchlist_match") or t.get("filer") or "") for t in trades} - {""})
    return {
        "count": len(trades),
        "buys": len(buys),
        "sells": len(sells),
        "filers": filers,
        "top_buys": [{"symbol": s, "n": n} for s, n in buy_c.most_common(5)],
        "top_sells": [{"symbol": s, "n": n} for s, n in sell_c.most_common(5)],
    }


def pick_symbols(trades: list[dict[str, Any]], limit: int = MAX_SYMBOLS) -> list[str]:
    """Prefer buy-side frequency, then any remaining tickers."""
    buys = Counter()
    rest = Counter()
    for t in trades:
        sym = str(t.get("symbol") or "").upper()
        if not sym:
            continue
        if (t.get("side") or "").lower() == "buy":
            buys[sym] += 1
        else:
            rest[sym] += 1
    ordered: list[str] = []
    for pool in (buys, rest):
        for sym, _n in pool.most_common():
            if sym not in ordered:
                ordered.append(sym)
            if len(ordered) >= limit:
                return ordered
    return ordered[:limit]


def _latest_event(trades: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    rows = [t for t in trades if str(t.get("symbol") or "").upper() == symbol]
    if not rows:
        return None

    def key(t: dict[str, Any]) -> str:
        return str(t.get("transaction_date") or t.get("disclosure_date") or "")

    buys = [t for t in rows if (t.get("side") or "").lower() == "buy"]
    pool = buys or rows
    return max(pool, key=key)


def _load_bars(symbol: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        from src.market_data import AlpacaMarketData

        bars = AlpacaMarketData().get_bars(symbol, limit=80)
        return bars, None
    except Exception as exc:
        log.warning("bars failed symbol=%s error=%s", symbol, exc)
        return [], friendly_feed_error(exc)


def research_watchlist_trades(
    trades: list[dict[str, Any]],
    *,
    max_symbols: int = MAX_SYMBOLS,
    fetch_reddit: bool = True,
    fetch_prices: bool = True,
) -> dict[str, Any]:
    """Per-ticker research bundle for the digest / MCP report."""
    summary = window_summary(trades)
    symbols = pick_symbols(trades, max_symbols)
    by_sym: dict[str, Any] = {}
    for i, sym in enumerate(symbols):
        sample = _latest_event(trades, sym) or {}
        inst = classify_instrument(sym, str(sample.get("asset") or ""))
        event_date = parse_event_date(sample) if sample else None
        if fetch_prices:
            bars, bar_err = _load_bars(sym)
            stats = price_stats(
                bars,
                event_date=event_date,
                side=sample.get("side"),
            )
            if bar_err and not stats.get("ok"):
                stats["error"] = bar_err
        else:
            stats = {"ok": False, "error": "skipped"}
        if fetch_reddit:
            if i:
                time.sleep(REDDIT_PAUSE_S)
            reddit = fetch_reddit_sentiment(
                sym,
                filer=str(sample.get("watchlist_match") or "") or None,
                sleep_s=REDDIT_PAUSE_S,
            )
        else:
            reddit = {"ok": False, "error": "skipped"}
        by_sym[sym] = {
            "instrument": inst,
            "stats": stats,
            "reddit": reddit,
            "filer": sample.get("watchlist_match"),
            "side": sample.get("side"),
            "amount": sample.get("amount"),
            "disclosure_date": sample.get("disclosure_date"),
            "transaction_date": sample.get("transaction_date"),
        }
    return {"window": summary, "symbols": by_sym}
