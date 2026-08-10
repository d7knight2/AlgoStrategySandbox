"""Broker abstraction interface."""

from abc import ABC, abstractmethod
from typing import Any


class Broker(ABC):
    """Abstract broker interface. Phase 1 implements read-only methods only."""

    @abstractmethod
    def get_account(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_orders(self, status: str = "open") -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_market_status(self) -> dict[str, Any]:
        ...

    # Explicitly NOT implemented in Phase 1:
    # submit_order, cancel_order, close_position
