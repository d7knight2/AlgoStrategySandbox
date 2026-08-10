"""FastAPI entrypoint — Phase 1–3 foundation (paper only, read-only + risk stub)."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from src.config import settings
from src.database import init_db
from src.broker import AlpacaBroker
from src.risk import RiskEngine, RiskLimits
from src.market_data import AlpacaMarketData
from src.signals import compute_basic_indicators

# Global risk engine instance (deterministic, non-overridable by AI)
risk_engine = RiskEngine(RiskLimits())


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AlgoStrategySandbox Trading Core",
    description="Phase 1–3 foundation — Paper trading only. Risk engine active.",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "phase": "1-3",
        "orders_enabled": False,
        "live_trading_enabled": False,
        "risk_engine": "active",
        "trading_paused": risk_engine.limits.trading_paused,
    }


@app.get("/account")
def account() -> dict[str, Any]:
    try:
        broker = AlpacaBroker()
        return broker.get_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/positions")
def positions() -> list[dict[str, Any]]:
    try:
        broker = AlpacaBroker()
        return broker.get_positions()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/orders")
def orders(status: str = "open") -> list[dict[str, Any]]:
    try:
        broker = AlpacaBroker()
        return broker.get_orders(status=status)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/market/status")
def market_status() -> dict[str, Any]:
    try:
        broker = AlpacaBroker()
        return broker.get_market_status()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/quote/{symbol}")
def quote(symbol: str) -> dict[str, Any]:
    try:
        md = AlpacaMarketData()
        return md.get_latest_quote(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/bars/{symbol}")
def bars(symbol: str, limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
    try:
        md = AlpacaMarketData()
        return md.get_bars(symbol.upper(), limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/signals/{symbol}")
def signals(symbol: str) -> dict[str, Any]:
    try:
        md = AlpacaMarketData()
        bar_data = md.get_bars(symbol.upper(), limit=100)
        return compute_basic_indicators(bar_data)
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


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse(
        {
            "message": "AlgoStrategySandbox Trading Core",
            "version": "0.2.0",
            "docs": "/docs",
            "health": "/health",
            "safety": {
                "trading_mode": "paper",
                "orders_enabled": False,
                "live_trading_enabled": False,
                "risk_engine": "active",
            },
        }
    )
