"""Alpaca PAPER broker implementation.

Read methods always available.
Order submission is available only when explicitly enabled and only in paper mode.
"""

from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

from src.broker.base import Broker
from src.config import settings


class AlpacaBroker(Broker):
    """Alpaca broker restricted to PAPER mode."""

    def __init__(self, allow_orders: bool = False) -> None:
        settings.validate_credentials()

        if not settings.is_paper:
            raise RuntimeError("Live trading is disabled")

        self._allow_orders = allow_orders
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

    def submit_market_order(
        self,
        symbol: str,
        side: str,
        qty: float | None = None,
        notional: float | None = None,
    ) -> dict[str, Any]:
        """Submit a market order — PAPER only, and only if allow_orders=True."""
        if not self._allow_orders:
            raise RuntimeError("Order submission is disabled on this broker instance")
        if not settings.is_paper:
            raise RuntimeError("Live order submission is forbidden")

        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        if qty is not None:
            req = MarketOrderRequest(
                symbol=symbol.upper(),
                qty=qty,
                side=side_enum,
                time_in_force=TimeInForce.DAY,
            )
        elif notional is not None:
            req = MarketOrderRequest(
                symbol=symbol.upper(),
                notional=notional,
                side=side_enum,
                time_in_force=TimeInForce.DAY,
            )
        else:
            raise ValueError("Provide qty or notional")

        order = self._client.submit_order(req)
        return {
            "id": str(order.id),
            "symbol": order.symbol,
            "side": str(order.side),
            "qty": float(order.qty) if order.qty else None,
            "notional": float(order.notional) if getattr(order, "notional", None) else None,
            "type": str(order.type),
            "status": str(order.status),
            "submitted_at": str(order.submitted_at),
        }
