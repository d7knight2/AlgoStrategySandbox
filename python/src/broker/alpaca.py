"""Alpaca PAPER broker implementation (read-only for Phase 1)."""

from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

from src.config import settings
from src.broker.base import Broker


class AlpacaBroker(Broker):
    """Alpaca broker restricted to PAPER mode and read-only operations."""

    def __init__(self) -> None:
        settings.validate_credentials()

        if not settings.is_paper:
            raise RuntimeError("Live trading is disabled in Phase 1")

        # paper=True is the critical safety flag
        self._client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=True,
        )

    def get_account(self) -> dict[str, Any]:
        account = self._client.get_account()
        return {
            "id": str(account.id),
            "status": str(account.status),
            "currency": account.currency,
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
            "equity": float(account.equity),
            "pattern_day_trader": account.pattern_day_trader,
            "trading_blocked": account.trading_blocked,
            "account_blocked": account.account_blocked,
            "created_at": str(account.created_at),
        }

    def get_positions(self) -> list[dict[str, Any]]:
        positions = self._client.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "side": str(p.side),
                "market_value": float(p.market_value),
                "avg_entry_price": float(p.avg_entry_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
                "current_price": float(p.current_price),
            }
            for p in positions
        ]

    def get_orders(self, status: str = "open") -> list[dict[str, Any]]:
        status_map = {
            "open": QueryOrderStatus.OPEN,
            "closed": QueryOrderStatus.CLOSED,
            "all": QueryOrderStatus.ALL,
        }
        req = GetOrdersRequest(status=status_map.get(status, QueryOrderStatus.OPEN))
        orders = self._client.get_orders(filter=req)
        return [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "side": str(o.side),
                "qty": float(o.qty) if o.qty else None,
                "filled_qty": float(o.filled_qty) if o.filled_qty else 0.0,
                "type": str(o.type),
                "status": str(o.status),
                "submitted_at": str(o.submitted_at),
            }
            for o in orders
        ]

    def get_market_status(self) -> dict[str, Any]:
        clock = self._client.get_clock()
        return {
            "is_open": clock.is_open,
            "next_open": str(clock.next_open),
            "next_close": str(clock.next_close),
            "timestamp": str(clock.timestamp),
        }
