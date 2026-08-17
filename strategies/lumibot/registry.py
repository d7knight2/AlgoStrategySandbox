"""Strategy registry mapping catalog ids to Lumibot strategy classes."""

from __future__ import annotations

from typing import Type

from lumibot.strategies.strategy import Strategy

from mean_reversion_rsi import RsiMeanReversionStrategy
from orb_strategy import OpeningRangeBreakoutStrategy
from sma_regime_rotation import SmaRegimeRotationStrategy

STRATEGY_REGISTRY: dict[str, Type[Strategy]] = {
    "opening-range-breakout": OpeningRangeBreakoutStrategy,
    "sma-regime-rotation": SmaRegimeRotationStrategy,
    "mean-reversion-rsi": RsiMeanReversionStrategy,
}

STRATEGY_FILES: dict[str, str] = {
    "opening-range-breakout": "orb_strategy.py",
    "sma-regime-rotation": "sma_regime_rotation.py",
    "mean-reversion-rsi": "mean_reversion_rsi.py",
}


def get_strategy_class(strategy_id: str) -> Type[Strategy]:
    if strategy_id not in STRATEGY_REGISTRY:
        known = ", ".join(sorted(STRATEGY_REGISTRY))
        raise KeyError(f"Unknown strategy '{strategy_id}'. Known strategies: {known}")
    return STRATEGY_REGISTRY[strategy_id]
