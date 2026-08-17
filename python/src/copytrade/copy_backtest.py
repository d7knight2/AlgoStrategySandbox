"""Historical backtest of copying a filer's public STOCK Act trades.

Uses disclosure/transaction dates + Alpaca IEX bars. Paper research only.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.feeds.congress import fetch_watchlist_trades, normalize_side, normalize_ticker
from src.market_data import AlpacaMarketData

log = logging.getLogger("trading_core.copy_backtest")


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


def _bars_index(symbol: str, limit: int = 500) -> list[dict[str, Any]]:
    try:
        bars = AlpacaMarketData().get_bars(symbol.upper(), limit=limit)
        return bars or []
    except Exception as exc:
        log.warning("bars failed symbol=%s err=%s", symbol, exc)
        return []


def _price_on_or_after(
    bars: list[dict[str, Any]], when: datetime
) -> tuple[float | None, str | None]:
    """First bar close on/after date (UTC-naive compare on date only)."""
    target = when.date()
    for b in bars:
        ts = b.get("timestamp")
        if ts is None:
            continue
        if hasattr(ts, "date"):
            d = ts.date()
        else:
            try:
                d = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).date()
            except Exception:
                continue
        if d >= target:
            return float(b["close"]), str(d)
    if bars:
        return float(bars[-1]["close"]), "last"
    return None, None


def backtest_copy_filer(
    filer: str,
    *,
    lookback_days: int = 365,
    starting_cash: float = 10_000.0,
    notional_per_trade: float = 1_000.0,
    use_disclosure_date: bool = True,
) -> dict[str, Any]:
    """Simulate fixed-notional copies of one filer's public PTRs.

    Entry timing:
      - use_disclosure_date=True (default): trade on disclosure date (realistic lag)
      - False: trade on transaction_date (optimistic / not tradable in practice)
    """
    trades = fetch_watchlist_trades([filer], lookback_days=lookback_days)
    # Sort chronologically by chosen date
    dated: list[tuple[datetime, dict[str, Any]]] = []
    for t in trades:
        raw = t.get("disclosure_date") if use_disclosure_date else t.get("transaction_date")
        dt = _parse_date(raw) or _parse_date(t.get("transaction_date"))
        if dt is None:
            continue
        dated.append((dt, t))
    dated.sort(key=lambda x: x[0])

    cash = starting_cash
    positions: dict[str, float] = {}  # symbol -> qty
    fills: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    bar_cache: dict[str, list[dict[str, Any]]] = {}

    def mark_equity(as_of: datetime) -> float:
        mkt = 0.0
        for sym, qty in positions.items():
            if qty <= 0:
                continue
            bars = bar_cache.setdefault(sym, _bars_index(sym))
            px, _ = _price_on_or_after(bars, as_of)
            if px:
                mkt += qty * px
        return cash + mkt

    for dt, t in dated:
        sym = normalize_ticker(t.get("symbol"))
        side = normalize_side(t.get("side")) or (t.get("side") or "").lower()
        if not sym or side not in ("buy", "sell"):
            continue
        bars = bar_cache.setdefault(sym, _bars_index(sym))
        px, px_day = _price_on_or_after(bars, dt)
        if not px or px <= 0:
            fills.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "symbol": sym,
                    "side": side,
                    "skipped": "no_price",
                }
            )
            continue

        if side == "buy":
            notional = min(notional_per_trade, cash)
            if notional < 25:
                fills.append(
                    {
                        "date": dt.strftime("%Y-%m-%d"),
                        "symbol": sym,
                        "side": side,
                        "skipped": "insufficient_cash",
                    }
                )
                continue
            qty = notional / px
            cash -= notional
            positions[sym] = positions.get(sym, 0.0) + qty
            fills.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "price_day": px_day,
                    "symbol": sym,
                    "side": "buy",
                    "qty": round(qty, 6),
                    "price": round(px, 4),
                    "notional": round(notional, 2),
                }
            )
        else:
            qty = positions.get(sym, 0.0)
            if qty <= 0:
                fills.append(
                    {
                        "date": dt.strftime("%Y-%m-%d"),
                        "symbol": sym,
                        "side": "sell",
                        "skipped": "flat",
                    }
                )
                continue
            proceeds = qty * px
            cash += proceeds
            positions[sym] = 0.0
            fills.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "price_day": px_day,
                    "symbol": sym,
                    "side": "sell",
                    "qty": round(qty, 6),
                    "price": round(px, 4),
                    "notional": round(proceeds, 2),
                }
            )

        eq = mark_equity(dt)
        equity_curve.append(
            {
                "t": dt.strftime("%Y-%m-%d"),
                "equity": round(eq, 2),
                "cash": round(cash, 2),
            }
        )

    end = datetime.utcnow()
    final_eq = mark_equity(end)
    ret = (final_eq - starting_cash) / starting_cash if starting_cash else 0.0

    peak = starting_cash
    max_dd = 0.0
    for pt in equity_curve:
        e = float(pt["equity"])
        peak = max(peak, e)
        if peak > 0:
            max_dd = max(max_dd, (peak - e) / peak)

    executed = [f for f in fills if not f.get("skipped")]
    return {
        "filer": filer,
        "lookback_days": lookback_days,
        "starting_cash": starting_cash,
        "notional_per_trade": notional_per_trade,
        "use_disclosure_date": use_disclosure_date,
        "signals": len(dated),
        "fills_executed": len(executed),
        "final_equity": round(final_eq, 2),
        "total_return_pct": round(ret * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "open_positions": {k: round(v, 6) for k, v in positions.items() if v > 0},
        "fills": fills[-40:],
        "equity_curve": equity_curve[-80:],
        "notes": [
            "Public delayed PTRs only — not financial advice.",
            "Default fills on disclosure date (tradable lag), not transaction date.",
            "Fixed notional per buy; sells flatten the virtual lot.",
            "Illustrative research — does not predict future edge.",
        ],
    }


def backtest_leaderboard(
    filers: list[str],
    *,
    lookback_days: int = 365,
    starting_cash: float = 10_000.0,
    notional_per_trade: float = 1_000.0,
) -> dict[str, Any]:
    rows = []
    for f in filers:
        try:
            r = backtest_copy_filer(
                f,
                lookback_days=lookback_days,
                starting_cash=starting_cash,
                notional_per_trade=notional_per_trade,
            )
            rows.append(
                {
                    "filer": f,
                    "total_return_pct": r["total_return_pct"],
                    "max_drawdown_pct": r["max_drawdown_pct"],
                    "fills_executed": r["fills_executed"],
                    "final_equity": r["final_equity"],
                    "equity_curve": r["equity_curve"],
                }
            )
        except Exception as exc:
            rows.append({"filer": f, "error": str(exc)[:200]})
    rows.sort(
        key=lambda x: (x.get("total_return_pct") is None, -(x.get("total_return_pct") or -1e9))
    )
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "lookback_days": lookback_days,
        "starting_cash": starting_cash,
        "notional_per_trade": notional_per_trade,
        "leaderboard": rows,
    }
