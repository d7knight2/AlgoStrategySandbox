"""FastAPI entrypoint — Phase 1 health + read-only broker endpoints."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.config import settings
from src.database import init_db
from src.broker import AlpacaBroker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown (nothing special yet)


app = FastAPI(
    title="AlgoStrategySandbox Trading Core",
    description="Phase 1 — Paper trading foundation (read-only)",
    version="0.1.0-phase1",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "phase": 1,
        "orders_enabled": False,
        "live_trading_enabled": False,
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


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse(
        {
            "message": "AlgoStrategySandbox Trading Core — Phase 1",
            "docs": "/docs",
            "health": "/health",
            "safety": {
                "trading_mode": "paper",
                "orders_enabled": False,
                "live_trading_enabled": False,
            },
        }
    )
