"""Shared risk and position-sizing helpers for Lumibot strategy templates."""

from __future__ import annotations


def position_size_by_risk(
    cash: float, risk_fraction: float, entry: float, stop: float
) -> int:
    stop_distance = max(abs(entry - stop), 0.01)
    risk_capital = cash * risk_fraction
    return int(risk_capital / stop_distance)


def capped_weight(weight: float, max_weight: float) -> float:
    return min(weight, max_weight)


def split_take_profit_quantities(total_qty: int) -> tuple[int, int]:
    """Split a position into two partial take-profit tranches."""
    if total_qty <= 1:
        return total_qty, 0
    first = total_qty // 2
    return first, total_qty - first
