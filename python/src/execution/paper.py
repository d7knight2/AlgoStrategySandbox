"""Paper execution path — proposals must pass RiskEngine.

- propose_and_validate: always available, records only
- execute_approved: submits to Alpaca PAPER only after RiskEngine ALLOW
"""

from typing import Any
import json
from datetime import datetime

from src.broker import AlpacaBroker
from src.risk import RiskEngine, ProposedTrade, RiskDecision
from src.database.session import SessionLocal
from src.database.models import TradeProposal, SignalRecord, SystemEvent, TradeFill
from src.config import settings


class PaperExecutionEngine:
    """Coordinates signal → risk → optional paper order."""

    def __init__(self, risk_engine: RiskEngine | None = None):
        self.risk = risk_engine or RiskEngine()
        # Read-only broker for account/positions
        self.broker = AlpacaBroker(allow_orders=False)
        # Separate client only used when we explicitly execute
        self._order_broker: AlpacaBroker | None = None

    def _order_client(self) -> AlpacaBroker:
        if self._order_broker is None:
            self._order_broker = AlpacaBroker(allow_orders=True)
        return self._order_broker

    def propose_and_validate(
        self,
        symbol: str,
        side: str,
        notional: float | None = None,
        qty: float | None = None,
        strategy_version: str = "v001",
        signal_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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

            db.add(SystemEvent(
                event_type="trade_proposal",
                message=(
                    f"{trade.side.upper()} {trade.symbol} "
                    f"notional={trade.notional} → {risk_result.decision.value}"
                ),
            ))
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
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def execute_approved(
        self,
        symbol: str,
        side: str,
        notional: float | None = None,
        qty: float | None = None,
        strategy_version: str = "v001",
        signal_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Propose → risk check → if ALLOW, submit PAPER market order.

        Still refuses to run if TRADING_MODE is not paper.
        """
        if not settings.is_paper:
            return {"error": "Live trading is forbidden", "executed": False}

        proposal = self.propose_and_validate(
            symbol=symbol,
            side=side,
            notional=notional,
            qty=qty,
            strategy_version=strategy_version,
            signal_meta=signal_meta,
        )

        if proposal.get("risk_decision") != RiskDecision.ALLOW.value:
            proposal["executed"] = False
            proposal["note"] = "Rejected by RiskEngine — no order submitted"
            return proposal

        try:
            order = self._order_client().submit_market_order(
                symbol=symbol,
                side=side,
                qty=qty,
                notional=notional,
            )
        except Exception as e:
            proposal["executed"] = False
            proposal["error"] = str(e)
            proposal["note"] = "Risk ALLOWED but order submission failed"
            return proposal

        # Record fill + mark proposal executed
        db = SessionLocal()
        try:
            fill = TradeFill(
                symbol=symbol.upper(),
                side=side.lower(),
                qty=float(order.get("qty") or qty or 0),
                price=0.0,  # fill price may arrive later via order update
                notional=float(notional or 0),
                order_id=order.get("id"),
                fees=0.0,
                strategy_version=strategy_version,
                mode="paper",
            )
            db.add(fill)

            prop = db.get(TradeProposal, proposal["proposal_id"])
            if prop:
                prop.executed = True

            db.add(SystemEvent(
                event_type="paper_order_submitted",
                message=f"PAPER {side.upper()} {symbol.upper()} order_id={order.get('id')}",
            ))
            db.commit()
        finally:
            db.close()

        self.risk.record_trade()

        proposal["executed"] = True
        proposal["order"] = order
        proposal["note"] = "Paper market order submitted after RiskEngine ALLOW"
        return proposal
