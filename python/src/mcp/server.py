"""Trading Core MCP Server (FastMCP).

Read-only + proposal + paper-execute (risk-gated) tools.
No live trading. No unrestricted order submission.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.config import settings
from src.broker import AlpacaBroker
from src.market_data import AlpacaMarketData
from src.signals import compute_basic_indicators, score_from_indicators
from src.risk import RiskEngine, RiskLimits
from src.execution import PaperExecutionEngine
from src.backtest import simple_backtest
from src.database import init_db

mcp = FastMCP(
    "trading-core",
    instructions=(
        "Paper-trading research system. "
        "Proposals and paper execution are risk-gated. "
        "No live trading."
    ),
)

_risk = RiskEngine(RiskLimits())
_paper = PaperExecutionEngine(risk_engine=_risk)


def _safe(fn, *args, **kwargs) -> str:
    try:
        result = fn(*args, **kwargs)
        return json.dumps(result, default=str, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def get_health() -> str:
    """System health and safety flags."""
    return _safe(lambda: {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "orders_enabled": True,  # paper only, still risk-gated
        "live_trading_enabled": False,
        "risk_engine": "active",
        "trading_paused": _risk.limits.trading_paused,
    })


@mcp.tool()
def get_account() -> str:
    """Alpaca PAPER account summary."""
    return _safe(lambda: AlpacaBroker().get_account())


@mcp.tool()
def get_positions() -> str:
    """Current open positions."""
    return _safe(lambda: AlpacaBroker().get_positions())


@mcp.tool()
def get_orders(status: str = "open") -> str:
    """List orders. status: open | closed | all."""
    return _safe(lambda: AlpacaBroker().get_orders(status=status))


@mcp.tool()
def get_market_status() -> str:
    """Market open/close clock."""
    return _safe(lambda: AlpacaBroker().get_market_status())


@mcp.tool()
def get_quote(symbol: str) -> str:
    """Latest bid/ask quote."""
    return _safe(lambda: AlpacaMarketData().get_latest_quote(symbol.upper()))


@mcp.tool()
def get_bars(symbol: str, limit: int = 50) -> str:
    """Recent OHLCV bars."""
    limit = max(1, min(500, int(limit)))
    return _safe(lambda: AlpacaMarketData().get_bars(symbol.upper(), limit=limit))


@mcp.tool()
def get_signals(symbol: str) -> str:
    """Indicators + deterministic signal score."""
    def _run():
        bars = AlpacaMarketData().get_bars(symbol.upper(), limit=100)
        indicators = compute_basic_indicators(bars)
        score = score_from_indicators(indicators)
        return {"symbol": symbol.upper(), "indicators": indicators, "score": score}
    return _safe(_run)


@mcp.tool()
def get_risk_status() -> str:
    """Hard risk limits and kill-switch state."""
    return _safe(lambda: {
        "trading_paused": _risk.limits.trading_paused,
        "limits": {
            "max_position_percent": _risk.limits.max_position_percent,
            "max_order_dollars": _risk.limits.max_order_dollars,
            "max_trades_per_day": _risk.limits.max_trades_per_day,
            "allow_shorting": _risk.limits.allow_shorting,
        },
        "trades_today": _risk._trades_today,
    })


@mcp.tool()
def run_backtest(symbol: str, limit: int = 200, initial_cash: float = 10000.0) -> str:
    """Chronological backtest (illustrative only)."""
    limit = max(60, min(1000, int(limit)))
    def _run():
        bars = AlpacaMarketData().get_bars(symbol.upper(), limit=limit)
        result = simple_backtest(bars, initial_cash=float(initial_cash))
        result["symbol"] = symbol.upper()
        result["bars_used"] = len(bars)
        return result
    return _safe(_run)


@mcp.tool()
def propose_trade(
    symbol: str,
    side: str,
    notional: float | None = None,
    qty: float | None = None,
    strategy_version: str = "v001",
) -> str:
    """Propose a trade (risk-checked, recorded, NOT executed)."""
    side = side.lower()
    if side not in ("buy", "sell"):
        return json.dumps({"error": "side must be buy or sell"})
    if notional is None and qty is None:
        return json.dumps({"error": "provide notional or qty"})

    def _run():
        signal_meta = None
        try:
            bars = AlpacaMarketData().get_bars(symbol.upper(), limit=100)
            signal_meta = score_from_indicators(compute_basic_indicators(bars))
        except Exception:
            pass
        return _paper.propose_and_validate(
            symbol=symbol, side=side, notional=notional, qty=qty,
            strategy_version=strategy_version, signal_meta=signal_meta,
        )
    return _safe(_run)


@mcp.tool()
def execute_paper_trade(
    symbol: str,
    side: str,
    notional: float | None = None,
    qty: float | None = None,
    strategy_version: str = "v001",
) -> str:
    """Risk-check then submit a PAPER market order if ALLOWED.

    Still refuses live mode. Kill switch and all hard limits apply.
    """
    side = side.lower()
    if side not in ("buy", "sell"):
        return json.dumps({"error": "side must be buy or sell"})
    if notional is None and qty is None:
        return json.dumps({"error": "provide notional or qty"})

    def _run():
        signal_meta = None
        try:
            bars = AlpacaMarketData().get_bars(symbol.upper(), limit=100)
            signal_meta = score_from_indicators(compute_basic_indicators(bars))
        except Exception:
            pass
        return _paper.execute_approved(
            symbol=symbol, side=side, notional=notional, qty=qty,
            strategy_version=strategy_version, signal_meta=signal_meta,
        )
    return _safe(_run)


@mcp.tool()
def risk_pause() -> str:
    """Emergency kill switch."""
    _risk.pause_trading()
    return json.dumps({"status": "trading paused"})


@mcp.tool()
def risk_resume() -> str:
    """Clear kill switch."""
    _risk.resume_trading()
    return json.dumps({"status": "trading resumed"})


def main() -> None:
    init_db()
    mcp.run()


if __name__ == "__main__":
    main()
