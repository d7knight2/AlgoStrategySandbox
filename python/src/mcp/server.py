"""Trading Core MCP Server (FastMCP).

Read-only + proposal + paper-execute (risk-gated) tools.
Ops helpers: health (API), Telegram test, research scan, risk pause/resume.
No live trading. No unrestricted order submission.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from src.backtest import simple_backtest
from src.broker import AlpacaBroker
from src.config import settings
from src.database import init_db
from src.execution import PaperExecutionEngine
from src.market_data import AlpacaMarketData
from src.notifications import send_telegram, telegram_configured
from src.research.loop import scan_universe
from src.risk import RiskEngine, RiskLimits
from src.signals import compute_basic_indicators, score_from_indicators

mcp = FastMCP(
    "trading-core",
    instructions=(
        "Paper-trading research system. "
        "Proposals and paper execution are risk-gated. "
        "Ops tools can check API health, test Telegram, run propose-only scans. "
        "No live trading."
    ),
)

_risk = RiskEngine(RiskLimits())
_paper = PaperExecutionEngine(risk_engine=_risk)

API_BASE = "http://127.0.0.1:8080"


def _safe(fn, *args, **kwargs) -> str:
    try:
        result = fn(*args, **kwargs)
        return json.dumps(result, default=str, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def _api_get(path: str) -> dict[str, Any]:
    with httpx.Client(timeout=15.0) as client:
        r = client.get(f"{API_BASE}{path}")
        r.raise_for_status()
        return r.json()


def _api_post(path: str, params: dict | None = None) -> dict[str, Any]:
    with httpx.Client(timeout=60.0) as client:
        r = client.post(f"{API_BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
def get_health() -> str:
    """Local process safety flags (does not require API to be up)."""
    return _safe(
        lambda: {
            "status": "ok",
            "trading_mode": settings.trading_mode,
            "orders_enabled": True,
            "live_trading_enabled": False,
            "risk_engine": "active",
            "trading_paused": _risk.limits.trading_paused,
            "telegram_configured": telegram_configured(),
            "api_base": API_BASE,
        }
    )


@mcp.tool()
def api_health() -> str:
    """Hit the running Trading Core HTTP API /health (dashboard backend on :8080)."""
    return _safe(_api_get, "/health")


@mcp.tool()
def dashboard_url() -> str:
    """Return Tailscale/local URLs for the dashboard."""

    def _urls():
        import subprocess

        ts = None
        try:
            ts = (
                subprocess.check_output(["tailscale", "ip", "-4"], text=True)
                .strip()
                .splitlines()[0]
            )
        except Exception:
            pass
        return {
            "local": "http://127.0.0.1:8080/dashboard",
            "tailscale": f"http://{ts}:8080/dashboard" if ts else None,
            "health": f"http://{ts or '127.0.0.1'}:8080/health",
            "ws": f"ws://{ts or '127.0.0.1'}:8080/ws/live",
            "note": "Open dashboard in Safari; live WS refreshes every ~5s. Hard-refresh if stale.",
        }

    return _safe(_urls)


@mcp.tool()
def telegram_debug() -> str:
    """Report whether Telegram env is set and send a test message if configured."""

    def _run():
        info = {
            "configured": telegram_configured(),
            "token_set": bool(settings.telegram_bot_token),
            "chat_id_set": bool(settings.telegram_chat_id),
            "chat_id_preview": (settings.telegram_chat_id[:4] + "…")
            if settings.telegram_chat_id
            else "",
        }
        if not telegram_configured():
            info["hint"] = (
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in /etc/alpaca/env or python/.env "
                "then restart the API process."
            )
            info["test"] = {"sent": False, "reason": "not configured"}
            return info
        # Prefer live API test so we know the running server has the env
        try:
            info["api_test"] = _api_post("/alerts/telegram/test")
        except Exception as e:
            info["api_test_error"] = str(e)
            info["direct_test"] = send_telegram(
                "<b>Trading Core MCP</b>\nDirect Telegram test (API may be down)."
            )
        return info

    return _safe(_run)


@mcp.tool()
def telegram_test() -> str:
    """Send a Telegram test alert via the running API (or direct if API down)."""

    def _run():
        try:
            return _api_post("/alerts/telegram/test")
        except Exception as e:
            return {
                "api_error": str(e),
                "direct": send_telegram(
                    "<b>Trading Core</b>\nTelegram test via MCP (API unreachable)."
                ),
            }

    return _safe(_run)


@mcp.tool()
def research_scan_mcp(max_notional: float = 100.0) -> str:
    """Propose-only universe scan + Telegram notify (no execute)."""
    return _safe(
        lambda: scan_universe(
            execute=False, max_notional=max_notional, notify=True
        )
    )


@mcp.tool()
def risk_pause() -> str:
    """Pause trading (kill switch) via API if up, else local engine."""

    def _run():
        try:
            return _api_post("/risk/pause")
        except Exception:
            _risk.pause_trading()
            send_telegram("<b>Trading PAUSED</b>\nVia MCP (API down path)")
            return {"status": "trading paused", "via": "local"}

    return _safe(_run)


@mcp.tool()
def risk_resume() -> str:
    """Resume trading via API if up, else local engine."""

    def _run():
        try:
            return _api_post("/risk/resume")
        except Exception:
            _risk.resume_trading()
            send_telegram("<b>Trading resumed</b>\nVia MCP (API down path)")
            return {"status": "trading resumed", "via": "local"}

    return _safe(_run)


@mcp.tool()
def get_account() -> str:
    """Alpaca PAPER account summary."""
    return _safe(lambda: AlpacaBroker().get_account())


@mcp.tool()
def get_positions() -> str:
    """Open PAPER positions."""
    return _safe(lambda: AlpacaBroker().get_positions())


@mcp.tool()
def get_market_status() -> str:
    """US market open/closed."""
    return _safe(lambda: AlpacaBroker().get_market_status())


@mcp.tool()
def get_quote(symbol: str) -> str:
    """Latest quote for symbol."""
    return _safe(lambda: AlpacaMarketData().get_latest_quote(symbol.upper()))


@mcp.tool()
def get_signals(symbol: str) -> str:
    """Indicators + signal score for symbol."""

    def _run():
        bars = AlpacaMarketData().get_bars(symbol.upper(), limit=100)
        ind = compute_basic_indicators(bars)
        score = score_from_indicators(ind)
        return {"symbol": symbol.upper(), "indicators": ind, "score": score}

    return _safe(_run)


@mcp.tool()
def propose_trade(
    symbol: str,
    side: str,
    notional: float = 100.0,
    execute: bool = False,
) -> str:
    """Risk-gated paper proposal; set execute=True only for paper fill."""

    def _run():
        init_db()
        if execute:
            return _paper.execute_approved(
                symbol=symbol,
                side=side,
                notional=notional,
                strategy_version="mcp_v001",
            )
        return _paper.propose_and_validate(
            symbol=symbol,
            side=side,
            notional=notional,
            strategy_version="mcp_v001",
        )

    return _safe(_run)


@mcp.tool()
def run_backtest(symbol: str, limit: int = 200, initial_cash: float = 10000.0) -> str:
    """Simple signal backtest on recent bars."""

    def _run():
        bars = AlpacaMarketData().get_bars(symbol.upper(), limit=limit)
        out = simple_backtest(bars, initial_cash=initial_cash)
        out["symbol"] = symbol.upper()
        return out

    return _safe(_run)


if __name__ == "__main__":
    mcp.run()
