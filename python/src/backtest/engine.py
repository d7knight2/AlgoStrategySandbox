"""Minimal chronological backtest engine (Phase 7 foundation).

Avoids look-ahead bias by iterating bars in time order.
This is intentionally simple so results are easy to audit.
"""

from typing import Any

from src.signals.indicators import compute_basic_indicators
from src.signals.scorer import score_from_indicators


def simple_backtest(
    bars: list[dict[str, Any]],
    initial_cash: float = 10_000.0,
    position_pct: float = 0.05,
    commission_per_trade: float = 0.0,
) -> dict[str, Any]:
    """Run a very simple long-only backtest on a list of OHLCV bars (oldest → newest).

    Rules:
    - Uses only information available up to the current bar (no look-ahead).
    - Buys when score decision == BUY and flat.
    - Sells when score decision == SELL and long.
    - Position size = position_pct of current equity.
    """
    if len(bars) < 60:
        return {"error": "Need at least 60 bars for meaningful indicators"}

    cash = initial_cash
    position_qty = 0.0
    entry_price = 0.0
    trades: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []

    for i in range(50, len(bars)):  # start after enough history for SMA50
        window = bars[: i + 1]
        indicators = compute_basic_indicators(window)
        score = score_from_indicators(indicators)
        price = float(bars[i]["close"])
        ts = bars[i].get("timestamp")

        # Mark-to-market equity
        equity = cash + position_qty * price
        equity_curve.append({"timestamp": ts, "equity": round(equity, 2)})

        decision = score["decision"]

        if decision == "BUY" and position_qty == 0:
            notional = equity * position_pct
            qty = notional / price if price > 0 else 0
            if qty > 0 and cash >= notional + commission_per_trade:
                cash -= notional + commission_per_trade
                position_qty = qty
                entry_price = price
                trades.append(
                    {
                        "timestamp": ts,
                        "side": "buy",
                        "price": price,
                        "qty": round(qty, 6),
                        "notional": round(notional, 2),
                        "signal_score": score["signal_score"],
                    }
                )

        elif decision == "SELL" and position_qty > 0:
            notional = position_qty * price
            cash += notional - commission_per_trade
            pnl = (price - entry_price) * position_qty - commission_per_trade
            trades.append(
                {
                    "timestamp": ts,
                    "side": "sell",
                    "price": price,
                    "qty": round(position_qty, 6),
                    "notional": round(notional, 2),
                    "pnl": round(pnl, 2),
                    "signal_score": score["signal_score"],
                }
            )
            position_qty = 0.0
            entry_price = 0.0

    # Final equity
    final_price = float(bars[-1]["close"])
    final_equity = cash + position_qty * final_price
    total_return = (final_equity - initial_cash) / initial_cash

    wins = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) < 0]

    return {
        "initial_cash": initial_cash,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return * 100, 2),
        "num_trades": len(trades),
        "num_round_trips": len([t for t in trades if t["side"] == "sell"]),
        "win_rate": round(len(wins) / max(1, len(wins) + len(losses)), 3),
        "trades": trades[-20:],  # last 20 for brevity
        "equity_curve_tail": equity_curve[-30:],
        "notes": [
            "Simple long-only rule based on deterministic scorer",
            "No look-ahead bias (indicators computed on past bars only)",
            "Results are illustrative only — not evidence of future edge",
        ],
    }
