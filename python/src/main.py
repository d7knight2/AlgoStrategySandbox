"""FastAPI entrypoint — Phase 1–7 foundation (paper only, risk-gated)."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.config import settings
from src.database import init_db
from src.broker import AlpacaBroker
from src.risk import RiskEngine, RiskLimits
from src.market_data import AlpacaMarketData
from src.signals import compute_basic_indicators, score_from_indicators
from src.execution import PaperExecutionEngine
from src.backtest import simple_backtest

# Global risk engine (deterministic, non-overridable by AI)
risk_engine = RiskEngine(RiskLimits())
paper_engine = PaperExecutionEngine(risk_engine=risk_engine)


class ProposeTradeRequest(BaseModel):
    symbol: str
    side: str = Field(..., pattern="^(buy|sell|BUY|SELL)$")
    notional: float | None = Field(None, gt=0)
    qty: float | None = Field(None, gt=0)
    strategy_version: str = "v001"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AlgoStrategySandbox Trading Core",
    description="Phase 1–7 foundation — Paper trading only. Hard risk engine active. No live orders.",
    version="0.3.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "phase": "1-7",
        "orders_enabled": False,
        "live_trading_enabled": False,
        "risk_engine": "active",
        "trading_paused": risk_engine.limits.trading_paused,
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
        md = AlpacaMarketData()
        bar_data = md.get_bars(symbol.upper(), limit=100)
        indicators = compute_basic_indicators(bar_data)
        score = score_from_indicators(indicators)
        return {
            "symbol": symbol.upper(),
            "indicators": indicators,
            "score": score,
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
    """Propose a trade. It is validated by the hard RiskEngine and recorded.

    No order is submitted in this phase.
    """
    if body.notional is None and body.qty is None:
        raise HTTPException(status_code=400, detail="Provide notional or qty")
    try:
        # Optionally enrich with current signal
        signal_meta = None
        try:
            md = AlpacaMarketData()
            bars = md.get_bars(body.symbol.upper(), limit=100)
            indicators = compute_basic_indicators(bars)
            signal_meta = score_from_indicators(indicators)
        except Exception:
            pass

        result = paper_engine.propose_and_validate(
            symbol=body.symbol,
            side=body.side,
            notional=body.notional,
            qty=body.qty,
            strategy_version=body.strategy_version,
            signal_meta=signal_meta,
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
    """Run a simple chronological backtest on recent bars."""
    try:
        md = AlpacaMarketData()
        bar_data = md.get_bars(symbol.upper(), limit=limit)
        result = simple_backtest(bar_data, initial_cash=initial_cash)
        result["symbol"] = symbol.upper()
        result["bars_used"] = len(bar_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse(
        {
            "message": "AlgoStrategySandbox Trading Core",
            "version": "0.3.0",
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
