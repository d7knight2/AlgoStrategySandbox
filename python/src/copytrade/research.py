"""Enrich STOCK Act rows with Reddit chatter, 7d/30d stats, and leverage flags."""

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from typing import Any

from src.copytrade.stats import parse_event_date, price_stats
from src.feeds.congress import _parse_date
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
    lags = [d for d in (disclosure_lag_days(t) for t in trades) if d is not None]
    return {
        "count": len(trades),
        "buys": len(buys),
        "sells": len(sells),
        "filers": filers,
        "top_buys": [{"symbol": s, "n": n} for s, n in buy_c.most_common(5)],
        "top_sells": [{"symbol": s, "n": n} for s, n in sell_c.most_common(5)],
        "median_lag_days": sorted(lags)[len(lags) // 2] if lags else None,
        "clusters": consensus_clusters(trades),
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


def disclosure_lag_days(trade: dict[str, Any]) -> int | None:
    """Days from transaction_date to disclosure_date (STOCK Act delay)."""
    traded = _parse_date(str(trade.get("transaction_date") or "") or None)
    disclosed = _parse_date(str(trade.get("disclosure_date") or "") or None)
    if traded is None or disclosed is None:
        return None
    return (disclosed.date() - traded.date()).days


def consensus_clusters(
    trades: list[dict[str, Any]],
    *,
    min_filers: int = 2,
) -> list[dict[str, Any]]:
    """Tickers bought or sold by two or more watchlist filers in the window."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        symbol = str(trade.get("symbol") or "").upper()
        side = (trade.get("side") or "").lower()
        filer = str(trade.get("watchlist_match") or trade.get("filer") or "").strip()
        if not symbol or side not in {"buy", "sell"} or not filer:
            continue
        groups[(symbol, side)].append(trade)
    out: list[dict[str, Any]] = []
    for (symbol, side), rows in groups.items():
        names = {str(r.get("watchlist_match") or r.get("filer") or "").strip() for r in rows}
        filers = sorted(names - {""})
        if len(filers) < min_filers:
            continue
        lags = [d for d in (disclosure_lag_days(r) for r in rows) if d is not None]
        out.append(
            {
                "symbol": symbol,
                "side": side,
                "filers": filers,
                "n_filers": len(filers),
                "n_trades": len(rows),
                "median_lag_days": sorted(lags)[len(lags) // 2] if lags else None,
            }
        )
    out.sort(key=lambda row: (-int(row["n_filers"]), -int(row["n_trades"]), str(row["symbol"])))
    return out


def cluster_filer_count(clusters: list[dict[str, Any]], symbol: str, side: str | None) -> int:
    want = (symbol or "").upper()
    want_side = (side or "").lower()
    for row in clusters:
        if row.get("symbol") == want and (not want_side or row.get("side") == want_side):
            return int(row.get("n_filers") or 0)
    return 1


def attention_score(
    *,
    instrument: dict[str, Any] | None = None,
    cluster_n: int = 1,
    lag_days: int | None = None,
    stats: dict[str, Any] | None = None,
    reddit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Operator attention rank. Does not size orders or set RiskEngine ALLOW."""
    inst = instrument or {}
    st = stats or {}
    rd = reddit or {}
    score = 50
    reasons: list[str] = []
    if cluster_n >= 3:
        score += 25
        reasons.append(f"{cluster_n} filers")
    elif cluster_n >= 2:
        score += 15
        reasons.append("2 filers")
    if inst.get("leveraged"):
        score -= 20
        reasons.append("leveraged ETF")
    if inst.get("direction") == "short":
        score -= 10
        reasons.append("inverse ETF")
    if lag_days is not None:
        if lag_days <= 14:
            score += 10
            reasons.append(f"fresh {lag_days}d lag")
        elif lag_days >= 40:
            score -= 10
            reasons.append(f"stale {lag_days}d lag")
    if st.get("fwd_7d_ready") and st.get("fwd_7d_pct") is not None:
        if float(st["fwd_7d_pct"]) > 0:
            score += 5
            reasons.append("7d after buy positive")
        else:
            score -= 5
            reasons.append("7d after buy negative")
    if rd.get("ok") and int(rd.get("gov_mentions") or 0) > 0:
        score += 5
        reasons.append("Reddit PTR chatter")
    score = max(0, min(100, score))
    return {
        "score": score,
        "reasons": reasons,
        "note": "attention only — does not size or execute copies",
    }


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
    clusters = summary.get("clusters") or consensus_clusters(trades)
    symbols = pick_symbols(trades, max_symbols)
    by_sym: dict[str, Any] = {}
    for i, sym in enumerate(symbols):
        sample = _latest_event(trades, sym) or {}
        inst = classify_instrument(sym, str(sample.get("asset") or ""))
        event_date = parse_event_date(sample) if sample else None
        lag = disclosure_lag_days(sample) if sample else None
        n_filers = cluster_filer_count(clusters, sym, sample.get("side"))
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
        attn = attention_score(
            instrument=inst,
            cluster_n=n_filers,
            lag_days=lag,
            stats=stats,
            reddit=reddit,
        )
        by_sym[sym] = {
            "instrument": inst,
            "stats": stats,
            "reddit": reddit,
            "attention": attn,
            "cluster_n": n_filers,
            "lag_days": lag,
            "filer": sample.get("watchlist_match"),
            "side": sample.get("side"),
            "amount": sample.get("amount"),
            "disclosure_date": sample.get("disclosure_date"),
            "transaction_date": sample.get("transaction_date"),
        }
    ranked = sorted(
        by_sym.items(),
        key=lambda kv: int((kv[1].get("attention") or {}).get("score") or 0),
        reverse=True,
    )
    return {
        "window": summary,
        "clusters": clusters,
        "attention": [
            {
                "symbol": sym,
                "score": (row.get("attention") or {}).get("score"),
                "reasons": (row.get("attention") or {}).get("reasons") or [],
                "side": row.get("side"),
            }
            for sym, row in ranked[:5]
        ],
        "symbols": by_sym,
        "notes": [
            "Attention scores are research context only.",
            "They do not size copies or bypass RiskEngine.",
        ],
    }
