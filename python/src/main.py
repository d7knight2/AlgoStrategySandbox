"""FastAPI entrypoint — paper trading core + rich dashboard."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.backtest import simple_backtest
from src.broker import AlpacaBroker
from src.config import settings
from src.database import init_db
from src.database.models import AccountSnapshot
from src.database.session import SessionLocal
from src.execution import PaperExecutionEngine
from src.market_data import AlpacaMarketData
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


class ProposeTradeRequest(BaseModel):
    symbol: str
    side: str = Field(..., pattern="^(buy|sell|BUY|SELL)$")
    notional: float | None = Field(None, gt=0)
    qty: float | None = Field(None, gt=0)
    strategy_version: str = "v001"
    execute: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AlgoStrategySandbox Trading Core",
    description="Paper trading · risk-gated · portfolio dashboard",
    version="0.6.0",
    lifespan=lifespan,
)

if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "version": "0.6.0",
        "orders_enabled": True,
        "live_trading_enabled": False,
        "risk_engine": "active",
        "trading_paused": risk_engine.limits.trading_paused,
        "email_configured": bool(settings.report_email_to and settings.smtp_host),
    }


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
    """Paper portfolio summary for the dashboard."""
    try:
        broker = AlpacaBroker()
        acct = broker.get_account()
        positions = broker.get_positions()

        # Store a snapshot for the equity curve
        db = SessionLocal()
        try:
            snap = AccountSnapshot(
                equity=float(acct.get("equity", 0)),
                cash=float(acct.get("cash", 0)),
                buying_power=float(acct.get("buying_power", 0)),
                portfolio_value=float(acct.get("portfolio_value", 0)),
            )
            db.add(snap)
            db.commit()

            history = (
                db.query(AccountSnapshot)
                .order_by(AccountSnapshot.created_at.asc())
                .limit(200)
                .all()
            )
        finally:
            db.close()

        equity_curve = [
            {
                "t": h.created_at.strftime("%m-%d %H:%M") if h.created_at else "",
                "v": float(h.equity),
            }
            for h in history
        ]

        day_pl = None
        if len(history) >= 2:
            day_pl = float(history[-1].equity) - float(history[0].equity)

        unrealized = sum(float(p.get("unrealized_pl") or 0) for p in positions)

        return {
            "equity": float(acct.get("equity", 0)),
            "cash": float(acct.get("cash", 0)),
            "buying_power": float(acct.get("buying_power", 0)),
            "portfolio_value": float(acct.get("portfolio_value", 0)),
            "positions_count": len(positions),
            "unrealized_pl": unrealized,
            "day_pl": day_pl,
            "equity_curve": equity_curve,
            "strategies": [
                {"id": "research_v001", "name": "Signal scorer", "status": "active"},
                {"id": "sma_regime_rotation", "name": "SMA regime", "status": "research"},
                {"id": "orb_strategy", "name": "ORB", "status": "research"},
            ],
        }
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
def risk_pause() -> dict[str, str]:
    risk_engine.pause_trading()
    return {"status": "trading paused"}


@app.post("/risk/resume")
def risk_resume() -> dict[str, str]:
    risk_engine.resume_trading()
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
            return paper_engine.execute_approved(
                symbol=body.symbol,
                side=body.side,
                notional=body.notional,
                qty=body.qty,
                strategy_version=body.strategy_version,
                signal_meta=signal_meta,
            )
        return paper_engine.propose_and_validate(
            symbol=body.symbol,
            side=body.side,
            notional=body.notional,
            qty=body.qty,
            strategy_version=body.strategy_version,
            signal_meta=signal_meta,
        )
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
        report = generate_progress_report()
        email_result = {"email_sent": False}
        if send_email:
            email_result = send_report_email(report)
        return {**report, **email_result}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/research/scan")
def research_scan(execute: bool = False, max_notional: float = 100.0) -> dict[str, Any]:
    """Run one research-loop pass (propose only by default)."""
    try:
        return scan_universe(execute=execute, max_notional=max_notional)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse(
        {
            "message": "AlgoStrategySandbox Trading Core",
            "version": "0.6.0",
            "docs": "/docs",
            "dashboard": "/dashboard",
            "health": "/health",
            "safety": {
                "trading_mode": "paper",
                "live_trading_enabled": False,
                "risk_engine": "active",
            },
        }
    )
