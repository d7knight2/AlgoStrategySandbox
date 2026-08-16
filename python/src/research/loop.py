"""Scheduled research / paper loop (Phase 8 foundation).

Scans a small universe, scores signals, optionally proposes (or executes paper)
trades through the RiskEngine. Designed to be run by cron or systemd timer.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any

from src.broker import AlpacaBroker
from src.database import init_db
from src.database.models import AccountSnapshot, SystemEvent
from src.database.session import SessionLocal
from src.execution import PaperExecutionEngine
from src.market_data import AlpacaMarketData
from src.risk import RiskEngine, RiskLimits
from src.signals import compute_basic_indicators, score_from_indicators

DEFAULT_UNIVERSE = ["SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA"]


def snapshot_account(broker: AlpacaBroker) -> dict[str, Any]:
    acct = broker.get_account()
    db = SessionLocal()
    try:
        snap = AccountSnapshot(
            equity=float(acct["equity"]),
            cash=float(acct["cash"]),
            buying_power=float(acct["buying_power"]),
            portfolio_value=float(acct["portfolio_value"]),
        )
        db.add(snap)
        db.commit()
    finally:
        db.close()
    return acct


def scan_universe(
    symbols: list[str],
    execute: bool = False,
    max_notional: float = 100.0,
) -> dict[str, Any]:
    init_db()
    risk = RiskEngine(RiskLimits(max_order_dollars=max_notional))
    engine = PaperExecutionEngine(risk_engine=risk)
    broker = AlpacaBroker(allow_orders=False)
    md = AlpacaMarketData()

    market = broker.get_market_status()
    account = snapshot_account(broker)

    results: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    for symbol in symbols:
        try:
            bars = md.get_bars(symbol, limit=100)
            indicators = compute_basic_indicators(bars)
            score = score_from_indicators(indicators)
            entry = {"symbol": symbol, "score": score, "price": indicators.get("price")}
            results.append(entry)

            decision = score["decision"]
            if decision in ("BUY", "SELL") and score["confidence"] >= 0.4:
                if execute:
                    action = engine.execute_approved(
                        symbol=symbol,
                        side=decision.lower(),
                        notional=max_notional,
                        strategy_version="research_v001",
                        signal_meta=score,
                    )
                else:
                    action = engine.propose_and_validate(
                        symbol=symbol,
                        side=decision.lower(),
                        notional=max_notional,
                        strategy_version="research_v001",
                        signal_meta=score,
                    )
                actions.append(action)
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e)})

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "market_open": market.get("is_open"),
        "account_equity": account.get("equity"),
        "mode": "execute_paper" if execute else "propose_only",
        "signals": results,
        "actions": actions,
    }

    db = SessionLocal()
    try:
        db.add(
            SystemEvent(
                event_type="research_loop",
                message=json.dumps(
                    {
                        "symbols": len(symbols),
                        "actions": len(actions),
                        "execute": execute,
                    }
                ),
            )
        )
        db.commit()
    finally:
        db.close()

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Research / paper trading loop")
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_UNIVERSE)
    parser.add_argument("--execute", action="store_true", help="Submit paper orders if risk allows")
    parser.add_argument("--max-notional", type=float, default=100.0)
    args = parser.parse_args()

    report = scan_universe(
        symbols=args.symbols,
        execute=args.execute,
        max_notional=args.max_notional,
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
