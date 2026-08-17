"""Live dashboard snapshot builder for WebSocket pushes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.broker import AlpacaBroker
from src.config import settings
from src.database.models import AccountSnapshot
from src.database.session import SessionLocal
from src.risk import RiskEngine


def build_live_snapshot(risk_engine: RiskEngine) -> dict[str, Any]:
    """Collect a single push payload for connected dashboard clients."""
    broker = AlpacaBroker()
    account: dict[str, Any] = {}
    positions: list[dict[str, Any]] = []
    market: dict[str, Any] = {}
    errors: list[str] = []

    try:
        account = broker.get_account()
    except Exception as e:
        errors.append(f"account: {e}")
    try:
        positions = broker.get_positions()
    except Exception as e:
        errors.append(f"positions: {e}")
    try:
        market = broker.get_market_status()
    except Exception as e:
        errors.append(f"market: {e}")

    equity_curve: list[dict[str, Any]] = []
    day_pl = None
    if account:
        try:
            db = SessionLocal()
            try:
                snap = AccountSnapshot(
                    equity=float(account.get("equity", 0)),
                    cash=float(account.get("cash", 0)),
                    buying_power=float(account.get("buying_power", 0)),
                    portfolio_value=float(account.get("portfolio_value", 0)),
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
            if len(history) >= 2:
                day_pl = float(history[-1].equity) - float(history[0].equity)
        except Exception as e:
            errors.append(f"snapshot: {e}")

    unrealized = sum(float(p.get("unrealized_pl") or 0) for p in positions)

    return {
        "type": "snapshot",
        "ts": datetime.now(UTC).isoformat(),
        "health": {
            "status": "ok",
            "trading_mode": settings.trading_mode,
            "version": "0.7.0",
            "orders_enabled": True,
            "live_trading_enabled": False,
            "risk_engine": "active",
            "trading_paused": risk_engine.limits.trading_paused,
            "email_configured": bool(settings.report_email_to and settings.smtp_host),
        },
        "account": account,
        "positions": positions,
        "market": market,
        "risk": {
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
        },
        "summary": {
            "equity": float(account.get("equity", 0) or 0),
            "cash": float(account.get("cash", 0) or 0),
            "buying_power": float(account.get("buying_power", 0) or 0),
            "positions_count": len(positions),
            "unrealized_pl": unrealized,
            "day_pl": day_pl,
            "equity_curve": equity_curve,
        },
        "errors": errors,
    }
