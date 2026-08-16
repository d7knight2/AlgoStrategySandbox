"""Paper execution path — proposals must pass RiskEngine.

Phase 1–4: This engine records proposals and risk decisions.
It does NOT submit real orders yet. Order submission will be added
only after explicit approval and only while TRADING_MODE=paper.
"""

from typing import Any
import json
from datetime import datetime

from src.broker import AlpacaBroker
from src.risk import RiskEngine, ProposedTrade, RiskDecision
from src.database.session import SessionLocal
from src.database.models import TradeProposal, SignalRecord, SystemEvent


class PaperExecutionEngine:
    """Coordinates signal → risk → (future) paper order."""

    def __init__(self, risk_engine: RiskEngine | None = None):
        self.broker = AlpacaBroker()
        self.risk = risk_engine or RiskEngine()

    def propose_and_validate(
        self,
        symbol: str,
        side: str,
        notional: float | None = None,
        qty: float | None = None,
        strategy_version: str = "v001",
        signal_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a trade proposal, run it through the hard risk engine, and persist the result.

        Returns a structured result. Never submits an order in this phase.
        """
        account = self.broker.get_account()
        positions = self.broker.get_positions()

        portfolio_value = float(account.get("portfolio_value", 0))
        buying_power = float(account.get("buying_power", 0))

        trade = ProposedTrade(
            symbol=symbol.upper(),
            side=side.lower(),
            qty=qty,
            notional=notional,
        )

        risk_result = self.risk.evaluate(
            trade=trade,
            portfolio_value=portfolio_value,
            current_positions=positions,
            buying_power=buying_power,
        )

        # Persist proposal for full audit trail
        db = SessionLocal()
        try:
            proposal = TradeProposal(
                symbol=trade.symbol,
                side=trade.side,
                qty=trade.qty,
                notional=trade.notional,
                risk_decision=risk_result.decision.value,
                risk_reasons="; ".join(risk_result.reasons),
                executed=False,
                strategy_version=strategy_version,
            )
            db.add(proposal)

            if signal_meta:
                sig = SignalRecord(
                    symbol=trade.symbol,
                    signal_score=float(signal_meta.get("signal_score", 0)),
                    decision=signal_meta.get("decision", "HOLD"),
                    confidence=float(signal_meta.get("confidence", 0)),
                    indicators_json=json.dumps(signal_meta.get("components", {})),
                    strategy_version=strategy_version,
                )
                db.add(sig)

            event = SystemEvent(
                event_type="trade_proposal",
                message=(
                    f"{trade.side.upper()} {trade.symbol} "
                    f"notional={trade.notional} → {risk_result.decision.value}"
                ),
            )
            db.add(event)
            db.commit()
            proposal_id = proposal.id
        finally:
            db.close()

        return {
            "proposal_id": proposal_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "notional": trade.notional,
            "qty": trade.qty,
            "risk_decision": risk_result.decision.value,
            "risk_reasons": risk_result.reasons,
            "limits_snapshot": risk_result.limits_snapshot,
            "executed": False,
            "note": "Order submission is disabled in this phase. Proposal recorded only.",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
