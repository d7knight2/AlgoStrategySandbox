"""Deterministic Risk Engine — Phase 1/2 stub with hard limits.

This layer is intentionally simple and non-overridable by any AI component.
All proposed trades MUST pass through RiskEngine.evaluate() before execution.
"""

from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class RiskDecision(str, Enum):
    ALLOW = "ALLOW"
    REJECT = "REJECT"


@dataclass
class RiskLimits:
    """Hard limits — change only with explicit human approval."""

    max_position_percent: float = 5.0          # % of portfolio
    max_order_dollars: float = 250.0
    max_daily_loss_percent: float = 2.0
    max_trades_per_day: int = 10
    max_portfolio_exposure: float = 100.0      # %
    allow_options: bool = False
    allow_margin: bool = False
    allow_shorting: bool = False
    trading_paused: bool = False               # global kill switch


@dataclass
class ProposedTrade:
    symbol: str
    side: str                  # "buy" | "sell"
    qty: float | None = None
    notional: float | None = None
    order_type: str = "market"


@dataclass
class RiskResult:
    decision: RiskDecision
    reasons: list[str] = field(default_factory=list)
    limits_snapshot: dict[str, Any] = field(default_factory=dict)


class RiskEngine:
    """Hard risk gate. AI cannot bypass this class."""

    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()
        self._trades_today: int = 0
        self._daily_pnl: float = 0.0

    def pause_trading(self) -> None:
        """Emergency kill switch."""
        self.limits.trading_paused = True

    def resume_trading(self) -> None:
        self.limits.trading_paused = False

    def evaluate(
        self,
        trade: ProposedTrade,
        portfolio_value: float,
        current_positions: list[dict[str, Any]],
        buying_power: float,
    ) -> RiskResult:
        reasons: list[str] = []

        if self.limits.trading_paused:
            reasons.append("Global trading pause is active (kill switch)")

        if trade.side.lower() == "sell" and not self.limits.allow_shorting:
            # Allow closing long positions, but block intentional shorts for now
            pos = next((p for p in current_positions if p["symbol"] == trade.symbol), None)
            if pos is None or float(pos.get("qty", 0)) <= 0:
                reasons.append("Shorting is disabled")

        # Notional / size checks
        notional = trade.notional
        if notional is None and trade.qty is not None:
            # Caller should supply price when possible; conservative fallback
            notional = 0.0

        if notional is not None and notional > self.limits.max_order_dollars:
            reasons.append(
                f"Order notional ${notional:.2f} exceeds max_order_dollars "
                f"${self.limits.max_order_dollars:.2f}"
            )

        if portfolio_value > 0 and notional is not None:
            pct = (notional / portfolio_value) * 100
            if pct > self.limits.max_position_percent:
                reasons.append(
                    f"Position size {pct:.1f}% exceeds max_position_percent "
                    f"{self.limits.max_position_percent}%"
                )

        if self._trades_today >= self.limits.max_trades_per_day:
            reasons.append(
                f"Max trades per day ({self.limits.max_trades_per_day}) reached"
            )

        if buying_power < (notional or 0):
            reasons.append("Insufficient buying power")

        decision = RiskDecision.REJECT if reasons else RiskDecision.ALLOW

        return RiskResult(
            decision=decision,
            reasons=reasons,
            limits_snapshot={
                "max_position_percent": self.limits.max_position_percent,
                "max_order_dollars": self.limits.max_order_dollars,
                "max_trades_per_day": self.limits.max_trades_per_day,
                "trading_paused": self.limits.trading_paused,
                "trades_today": self._trades_today,
            },
        )

    def record_trade(self) -> None:
        """Call after a successful fill so daily counters stay accurate."""
        self._trades_today += 1
