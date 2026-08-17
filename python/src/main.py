"""FastAPI entrypoint — paper trading core + live WebSocket dashboard."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.backtest import simple_backtest
from src.broker import AlpacaBroker
from src.config import settings
from src.copytrade.engine import filer_watchlist, run_copytrade_daily
from src.database import init_db
from src.execution import PaperExecutionEngine
from src.market_data import AlpacaMarketData
from src.monitoring import metrics as prom_metrics
from src.monitoring.live import build_live_snapshot
from src.notifications import send_telegram, telegram_configured
from src.reporting import generate_progress_report, send_report_email
from src.research.loop import scan_universe
from src.risk import RiskEngine, RiskLimits
from src.signals import compute_basic_indicators, score_from_indicators

risk_engine = RiskEngine(RiskLimits())
paper_engine = PaperExecutionEngine(risk_engine=risk_engine)

MONITOR = Path(__file__).resolve().parent / "monitoring"
STATIC = MONITOR / "static"
TEMPLATES_DIR = MONITOR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_ws_clients: set[WebSocket] = set()
_ws_lock = asyncio.Lock()


class ProposeTradeRequest(BaseModel):
    symbol: str
    side: str = Field(..., pattern="^(buy|sell|BUY|SELL)$")
    notional: float | None = Field(None, gt=0)
    qty: float | None = Field(None, gt=0)
    strategy_version: str = "v001"
    execute: bool = False


async def _broadcast(payload: dict[str, Any]) -> None:
    data = json.dumps(payload, default=str)
    dead: list[WebSocket] = []
    async with _ws_lock:
        clients = list(_ws_clients)
    for ws in clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    if dead:
        async with _ws_lock:
            for ws in dead:
                _ws_clients.discard(ws)


async def _live_push_loop() -> None:
    while True:
        try:
            if _ws_clients:
                snap = await asyncio.to_thread(build_live_snapshot, risk_engine)
                await _broadcast(snap)
        except Exception as e:
            await _broadcast({"type": "error", "message": str(e)})
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(_live_push_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="AlgoStrategySandbox Trading Core",
    description="Paper trading · risk-gated · live WebSocket + Telegram alerts",
    version="0.9.0",
    lifespan=lifespan,
)

if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "version": "0.9.0",
        "orders_enabled": True,
        "live_trading_enabled": False,
        "risk_engine": "active",
        "trading_paused": risk_engine.limits.trading_paused,
        "email_configured": bool(settings.report_email_to and settings.smtp_host),
        "telegram_configured": telegram_configured(),
        "copytrade_execute_paper": settings.copytrade_execute_paper,
        "metrics_enabled": prom_metrics.metrics_enabled(),
        "ws_clients": len(_ws_clients),
    }


@app.get("/metrics")
def metrics_endpoint():
    """Prometheus scrape endpoint."""
    body, ctype = prom_metrics.render_metrics()
    prom_metrics.set_paused(risk_engine.limits.trading_paused)
    return Response(content=body, media_type=ctype)


@app.get("/account")
def account() -> dict[str, Any]:
    try:
        return AlpacaBroker().get_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/positions")
def positions() -> list[dict[str, Any]]:
    try:
        return AlpacaBroker().get_positions()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/orders")
def orders(status: str = "open") -> list[dict[str, Any]]:
    try:
        return AlpacaBroker().get_orders(status=status)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/market/status")
def market_status() -> dict[str, Any]:
    try:
        return AlpacaBroker().get_market_status()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/quote/{symbol}")
def quote(symbol: str) -> dict[str, Any]:
    try:
        return AlpacaMarketData().get_latest_quote(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/bars/{symbol}")
def bars(symbol: str, limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
    try:
        return AlpacaMarketData().get_bars(symbol.upper(), limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/signals/{symbol}")
def signals(symbol: str) -> dict[str, Any]:
    try:
        bar_data = AlpacaMarketData().get_bars(symbol.upper(), limit=100)
        indicators = compute_basic_indicators(bar_data)
        score = score_from_indicators(indicators)
        return {"symbol": symbol.upper(), "indicators": indicators, "score": score}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/portfolio/summary")
def portfolio_summary() -> dict[str, Any]:
    try:
        return build_live_snapshot(risk_engine)["summary"]
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/risk/status")
def risk_status() -> dict[str, Any]:
    return {
        "trading_paused": risk_engine.limits.trading_paused,
        "limits": {
            "max_position_percent": risk_engine.limits.max_position_percent,
            "max_order_dollars": risk_engine.limits.max_order_dollars,
            "max_daily_loss_percent": risk_engine.limits.max_daily_loss_percent,
            "max_trades_per_day": risk_engine.limits.max_trades_per_day,
            "allow_shorting": risk_engine.limits.allow_shorting,
            "allow_options": risk_engine.limits.allow_options,
            "allow_margin": risk_engine.limits.allow_margin,
        },
        "trades_today": risk_engine._trades_today,
    }


@app.post("/risk/pause")
async def risk_pause() -> dict[str, str]:
    risk_engine.pause_trading()
    prom_metrics.set_paused(True)
    await _broadcast({"type": "risk", "trading_paused": True})
    send_telegram("<b>Trading PAUSED</b>\nKill switch active · paper only")
    return {"status": "trading paused"}


@app.post("/risk/resume")
async def risk_resume() -> dict[str, str]:
    risk_engine.resume_trading()
    prom_metrics.set_paused(False)
    await _broadcast({"type": "risk", "trading_paused": False})
    send_telegram("<b>Trading resumed</b>\nKill switch cleared · paper only")
    return {"status": "trading resumed"}


@app.post("/propose_trade")
def propose_trade(body: ProposeTradeRequest) -> dict[str, Any]:
    if body.notional is None and body.qty is None:
        raise HTTPException(status_code=400, detail="Provide notional or qty")
    try:
        signal_meta = None
        try:
            bars_data = AlpacaMarketData().get_bars(body.symbol.upper(), limit=100)
            signal_meta = score_from_indicators(compute_basic_indicators(bars_data))
        except Exception:
            pass

        if body.execute:
            result = paper_engine.execute_approved(
                symbol=body.symbol,
                side=body.side,
                notional=body.notional,
                qty=body.qty,
                strategy_version=body.strategy_version,
                signal_meta=signal_meta,
            )
        else:
            result = paper_engine.propose_and_validate(
                symbol=body.symbol,
                side=body.side,
                notional=body.notional,
                qty=body.qty,
                strategy_version=body.strategy_version,
                signal_meta=signal_meta,
            )

        prom_metrics.note_risk(str(result.get("risk_decision") or ""))
        if result.get("risk_decision") == "ALLOW":
            send_telegram(
                f"<b>Trade proposal ALLOW</b>\n"
                f"{(body.side or '').upper()} <code>{body.symbol.upper()}</code>\n"
                f"notional={body.notional} qty={body.qty}\n"
                f"executed={result.get('executed')}\n"
                f"<i>Paper only</i>"
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/backtest/{symbol}")
def backtest(
    symbol: str,
    limit: int = Query(200, ge=60, le=1000),
    initial_cash: float = Query(10000.0, gt=0),
) -> dict[str, Any]:
    try:
        bar_data = AlpacaMarketData().get_bars(symbol.upper(), limit=limit)
        result = simple_backtest(bar_data, initial_cash=initial_cash)
        result["symbol"] = symbol.upper()
        result["bars_used"] = len(bar_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/reports/latest")
def reports_latest() -> dict[str, Any]:
    latest = Path("data/reports/latest.json")
    if not latest.exists():
        return {"error": "no report yet", "hint": "POST /reports/generate"}
    return json.loads(latest.read_text())


@app.post("/reports/generate")
def reports_generate(send_email: bool = True) -> dict[str, Any]:
    try:
        report = generate_progress_report(notify_telegram=True)
        email_result: dict[str, Any] = {"email_sent": False}
        if send_email:
            email_result = send_report_email(report)
        return {**report, **email_result}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/research/scan")
def research_scan(execute: bool = False, max_notional: float = 100.0) -> dict[str, Any]:
    try:
        prom_metrics.note_scan()
        return scan_universe(execute=execute, max_notional=max_notional, notify=True)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/copytrade/watchlist")
def copytrade_watchlist() -> dict[str, Any]:
    return {
        "filers": filer_watchlist(),
        "lookback_days": settings.copytrade_lookback_days,
        "max_notional": settings.copytrade_max_notional,
        "execute_paper": settings.copytrade_execute_paper,
        "notes": [
            "STOCK Act and 13F filings are public and delayed (often ~45 days).",
            "Paper copies use a fixed notional cap, not disclosed dollar size.",
            "Live trading is disabled.",
        ],
    }


@app.get("/copytrade/latest")
def copytrade_latest() -> dict[str, Any]:
    latest = Path("data/reports/copytrade_latest.json")
    if not latest.exists():
        return {"error": "no copytrade report yet", "hint": "POST /copytrade/run"}
    return json.loads(latest.read_text())


@app.post("/copytrade/run")
def copytrade_run(
    execute: bool | None = None,
    notify: bool = True,
    lookback_days: int | None = Query(None, ge=1, le=90),
    max_notional: float | None = Query(None, gt=0, le=500),
) -> dict[str, Any]:
    try:
        return run_copytrade_daily(
            execute=execute,
            notify=notify,
            lookback_days=lookback_days,
            max_notional=max_notional,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/alerts/telegram/test")
def telegram_test() -> dict[str, Any]:
    """Send a test Telegram message (requires TELEGRAM_* env)."""
    result = send_telegram(
        "<b>Trading Core</b>\nTelegram alerts are working.\n<i>Paper mode · risk engine active</i>"
    )
    prom_metrics.note_telegram(bool(result.get("sent")))
    return {"configured": telegram_configured(), **result}


@app.post("/telegram/command")
def telegram_command(
    text: str = Query(..., min_length=1, max_length=500),
    chat_id: str | None = None,
) -> dict[str, Any]:
    """Run an inbound Telegram command (same allowlist as the poller)."""
    from src.notifications.commands import handle_text

    cid = chat_id if chat_id is not None else str(settings.telegram_chat_id or "")
    reply = handle_text(text, chat_id=cid)
    return {"reply": reply, "ignored": reply == ""}


@app.get("/copytrade/books")
def copytrade_books() -> dict[str, Any]:
    from src.copytrade.books import list_book_snapshots

    return {"books": list_book_snapshots(fetch_prices=False)}


@app.post("/copytrade/books")
def copytrade_create_book(
    filer: str = Query(..., min_length=3, max_length=128),
    starting_cash: float = Query(10000, ge=100, le=100000),
) -> dict[str, Any]:
    from src.copytrade.books import create_book

    return create_book(filer, starting_cash=starting_cash, auto_execute=True)


@app.post("/reports/weekly")
def reports_weekly(notify: bool = True) -> dict[str, Any]:
    from src.reporting.weekly import generate_weekly_report

    try:
        return generate_weekly_report(notify=notify)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await websocket.accept()
    async with _ws_lock:
        _ws_clients.add(websocket)
    try:
        snap = await asyncio.to_thread(build_live_snapshot, risk_engine)
        await websocket.send_text(json.dumps(snap, default=str))
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping", "ts": snap.get("ts")}))
                continue
            if msg in ("refresh", "ping", '{"type":"refresh"}'):
                snap = await asyncio.to_thread(build_live_snapshot, risk_engine)
                await websocket.send_text(json.dumps(snap, default=str))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        async with _ws_lock:
            _ws_clients.discard(websocket)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse(
        {
            "message": "AlgoStrategySandbox Trading Core",
            "version": "0.9.0",
            "docs": "/docs",
            "dashboard": "/dashboard",
            "ws": "/ws/live",
            "health": "/health",
            "metrics": "/metrics",
            "telegram": telegram_configured(),
            "safety": {
                "trading_mode": "paper",
                "live_trading_enabled": False,
                "risk_engine": "active",
            },
        }
    )
