"""Trading Core MCP Server (FastMCP).

Read-only + proposal + paper-execute (risk-gated) tools.
Ops helpers: health (API), Telegram test, research scan, risk pause/resume.
Failures are logged to stderr and data/reports/mcp.log with a request_id.
No live trading. No unrestricted order submission.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from src.backtest import simple_backtest
from src.broker import AlpacaBroker
from src.config import settings
from src.database import init_db
from src.execution import PaperExecutionEngine
from src.market_data import AlpacaMarketData
from src.mcp.tooling import (
    LOG_FILE,
    api_request,
    configure_logging,
    diagnostics,
    get_logger,
    hint_for,
    safe_tool,
)
from src.notifications import send_telegram, telegram_configured
from src.research.loop import scan_universe
from src.risk import RiskEngine, RiskLimits
from src.signals import compute_basic_indicators, score_from_indicators

configure_logging()

mcp = FastMCP(
    "trading-core",
    instructions=(
        "Paper-trading research system. "
        "Proposals and paper execution are risk-gated. "
        "Ops tools can check API health, test Telegram, run propose-only scans. "
        "On tool failure, read error_type/hint/request_id and data/reports/mcp.log. "
        "Use mcp_diagnostics first when something is broken. "
        "No live trading."
    ),
)

_risk = RiskEngine(RiskLimits())
_paper = PaperExecutionEngine(risk_engine=_risk)
log = get_logger()


def _fallback(tool: str, exc: BaseException, local: dict[str, Any]) -> dict[str, Any]:
    """Record that we used a local path because the HTTP API failed."""
    log.warning(
        "tool=%s falling back to local engine: %s: %s",
        tool,
        type(exc).__name__,
        exc,
    )
    return {
        **local,
        "via": "local",
        "api_error": str(exc)[:400],
        "error_type": type(exc).__name__,
        "hint": hint_for(exc),
    }


@mcp.tool()
def get_health() -> str:
    """Local process safety flags (does not require API to be up)."""
    return safe_tool(
        "get_health",
        lambda: {
            "status": "ok",
            "trading_mode": settings.trading_mode,
            "orders_enabled": True,
            "live_trading_enabled": False,
            "risk_engine": "active",
            "trading_paused": _risk.limits.trading_paused,
            "telegram_configured": telegram_configured(),
            "api_base": "http://127.0.0.1:8080",
            "log_file": str(LOG_FILE),
        },
    )


@mcp.tool()
def api_health() -> str:
    """Hit the running Trading Core HTTP API /health (dashboard backend on :8080)."""
    return safe_tool("api_health", api_request, "GET", "/health")


@mcp.tool()
def mcp_diagnostics() -> str:
    """API reachability, Telegram/Alpaca config flags, and recent MCP tool failures."""
    return safe_tool("mcp_diagnostics", diagnostics)


@mcp.tool()
def dashboard_url() -> str:
    """Return Tailscale/local URLs for the dashboard."""

    def _urls() -> dict[str, Any]:
        import subprocess

        ts = None
        tailscale_error = None
        try:
            ts = (
                subprocess.check_output(
                    ["tailscale", "ip", "-4"],
                    text=True,
                    stderr=subprocess.STDOUT,
                    timeout=5,
                )
                .strip()
                .splitlines()[0]
            )
        except Exception as exc:
            tailscale_error = f"{type(exc).__name__}: {exc}"
            log.warning("tailscale ip failed: %s", tailscale_error)
        return {
            "local": "http://127.0.0.1:8080/dashboard",
            "tailscale": f"http://{ts}:8080/dashboard" if ts else None,
            "health": f"http://{ts or '127.0.0.1'}:8080/health",
            "ws": f"ws://{ts or '127.0.0.1'}:8080/ws/live",
            "tailscale_error": tailscale_error,
            "note": "Open dashboard in Safari; live WS refreshes every ~5s. Hard-refresh if stale.",
        }

    return safe_tool("dashboard_url", _urls)


@mcp.tool()
def telegram_debug() -> str:
    """Report whether Telegram env is set and send a test message if configured."""

    def _run() -> dict[str, Any]:
        info: dict[str, Any] = {
            "configured": telegram_configured(),
            "token_set": bool(settings.telegram_bot_token),
            "chat_id_set": bool(settings.telegram_chat_id),
            "chat_id_preview": (settings.telegram_chat_id[:4] + "…")
            if settings.telegram_chat_id
            else "",
        }
        if not telegram_configured():
            log.warning("telegram_debug: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
            info["hint"] = (
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in /etc/alpaca/env or python/.env "
                "then restart the API process."
            )
            info["test"] = {"sent": False, "reason": "not configured"}
            return info
        try:
            info["api_test"] = api_request("POST", "/alerts/telegram/test", timeout=20.0)
        except Exception as exc:
            log.warning("telegram_debug API test failed: %s: %s", type(exc).__name__, exc)
            info["api_test_error"] = str(exc)[:400]
            info["api_error_type"] = type(exc).__name__
            info["hint"] = hint_for(exc)
            info["direct_test"] = send_telegram(
                "<b>Trading Core MCP</b>\nDirect Telegram test (API may be down)."
            )
        return info

    return safe_tool("telegram_debug", _run)


@mcp.tool()
def telegram_test() -> str:
    """Send a Telegram test alert via the running API (or direct if API down)."""

    def _run() -> dict[str, Any]:
        try:
            return api_request("POST", "/alerts/telegram/test", timeout=20.0)
        except Exception as exc:
            log.warning("telegram_test API failed, trying direct send: %s", exc)
            return _fallback(
                "telegram_test",
                exc,
                {
                    "direct": send_telegram(
                        "<b>Trading Core</b>\nTelegram test via MCP (API unreachable)."
                    )
                },
            )

    return safe_tool("telegram_test", _run)


@mcp.tool()
def research_scan_mcp(max_notional: float = 100.0) -> str:
    """Propose-only universe scan + Telegram notify (no execute). Prefers the API."""

    def _run() -> dict[str, Any]:
        try:
            return api_request(
                "POST",
                "/research/scan",
                params={"max_notional": max_notional, "execute": False},
                timeout=60.0,
            )
        except Exception as exc:
            report = scan_universe(execute=False, max_notional=max_notional, notify=True)
            return _fallback("research_scan_mcp", exc, report)

    return safe_tool("research_scan_mcp", _run)


@mcp.tool()
def risk_pause() -> str:
    """Pause trading (kill switch) via API if up, else local engine."""

    def _run() -> dict[str, Any]:
        try:
            return api_request("POST", "/risk/pause")
        except Exception as exc:
            _risk.pause_trading()
            send_telegram("<b>Trading PAUSED</b>\nVia MCP (API down path)")
            return _fallback("risk_pause", exc, {"status": "trading paused"})

    return safe_tool("risk_pause", _run)


@mcp.tool()
def risk_resume() -> str:
    """Resume trading via API if up, else local engine."""

    def _run() -> dict[str, Any]:
        try:
            return api_request("POST", "/risk/resume")
        except Exception as exc:
            _risk.resume_trading()
            send_telegram("<b>Trading resumed</b>\nVia MCP (API down path)")
            return _fallback("risk_resume", exc, {"status": "trading resumed"})

    return safe_tool("risk_resume", _run)


@mcp.tool()
def get_risk_status() -> str:
    """Kill-switch and limits. Prefers the running API so pause state is shared."""

    def _run() -> dict[str, Any]:
        try:
            return api_request("GET", "/risk/status")
        except Exception as exc:
            return _fallback(
                "get_risk_status",
                exc,
                {
                    "trading_paused": _risk.limits.trading_paused,
                    "limits": {
                        "max_order_dollars": _risk.limits.max_order_dollars,
                        "max_trades_per_day": _risk.limits.max_trades_per_day,
                    },
                    "trades_today": _risk._trades_today,
                },
            )

    return safe_tool("get_risk_status", _run)


@mcp.tool()
def get_account() -> str:
    """Alpaca PAPER account summary."""
    return safe_tool("get_account", lambda: AlpacaBroker().get_account())


@mcp.tool()
def get_positions() -> str:
    """Open PAPER positions."""
    return safe_tool("get_positions", lambda: AlpacaBroker().get_positions())


@mcp.tool()
def get_orders(status: str = "open") -> str:
    """Paper orders (open/closed/all)."""
    return safe_tool("get_orders", lambda: AlpacaBroker().get_orders(status=status))


@mcp.tool()
def get_market_status() -> str:
    """US market open/closed."""
    return safe_tool("get_market_status", lambda: AlpacaBroker().get_market_status())


@mcp.tool()
def get_quote(symbol: str) -> str:
    """Latest quote for symbol."""
    return safe_tool("get_quote", lambda: AlpacaMarketData().get_latest_quote(symbol.upper()))


@mcp.tool()
def get_bars(symbol: str, limit: int = 50) -> str:
    """Recent daily bars for symbol."""
    return safe_tool("get_bars", lambda: AlpacaMarketData().get_bars(symbol.upper(), limit=limit))


@mcp.tool()
def get_signals(symbol: str) -> str:
    """Indicators + signal score for symbol."""

    def _run() -> dict[str, Any]:
        bars = AlpacaMarketData().get_bars(symbol.upper(), limit=100)
        ind = compute_basic_indicators(bars)
        score = score_from_indicators(ind)
        return {"symbol": symbol.upper(), "indicators": ind, "score": score}

    return safe_tool("get_signals", _run)


@mcp.tool()
def propose_trade(
    symbol: str,
    side: str,
    notional: float = 100.0,
    execute: bool = False,
) -> str:
    """Risk-gated paper proposal; set execute=True only for paper fill."""

    def _run() -> dict[str, Any]:
        log.info(
            "propose_trade symbol=%s side=%s notional=%s execute=%s",
            symbol,
            side,
            notional,
            execute,
        )
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

    return safe_tool("propose_trade", _run)


@mcp.tool()
def run_backtest(symbol: str, limit: int = 200, initial_cash: float = 10000.0) -> str:
    """Simple signal backtest on recent bars."""

    def _run() -> dict[str, Any]:
        bars = AlpacaMarketData().get_bars(symbol.upper(), limit=limit)
        out = simple_backtest(bars, initial_cash=initial_cash)
        out["symbol"] = symbol.upper()
        return out

    return safe_tool("run_backtest", _run)


if __name__ == "__main__":
    log.info("starting trading-core MCP stdio log_file=%s", LOG_FILE)
    mcp.run()
