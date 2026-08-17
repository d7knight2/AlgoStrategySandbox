"""Run all enabled paper copy rules (any filer) with weekly budgets."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.copytrade.books import create_book
from src.copytrade.rules import load_rules
from src.database import init_db
from src.database.models import CopyTradeSeen
from src.database.session import SessionLocal
from src.execution import PaperExecutionEngine
from src.feeds.congress import fetch_watchlist_trades
from src.notifications import send_telegram
from src.risk import RiskEngine, RiskLimits

log = logging.getLogger("trading_core.copytrade.weekly_allocate")
REPORTS = Path(__file__).resolve().parents[2] / "data" / "reports"
BUDGET_DIR = REPORTS / "rule_budgets"


def _iso_week() -> str:
    d = datetime.utcnow()
    return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"


def _budget_path(rule_id: str) -> Path:
    BUDGET_DIR.mkdir(parents=True, exist_ok=True)
    return BUDGET_DIR / f"{rule_id}.json"


def _load_budget(rule_id: str, weekly_budget: float) -> dict[str, Any]:
    week = _iso_week()
    path = _budget_path(rule_id)
    if path.is_file():
        try:
            data = json.loads(path.read_text())
            if data.get("week") == week:
                return data
        except Exception:
            pass
    return {"week": week, "budget": weekly_budget, "spent": 0.0, "fills": []}


def _save_budget(rule_id: str, data: dict[str, Any]) -> None:
    _budget_path(rule_id).write_text(json.dumps(data, indent=2, default=str))


def _seen(event_key: str) -> bool:
    db = SessionLocal()
    try:
        return db.query(CopyTradeSeen).filter(CopyTradeSeen.event_key == event_key).first() is not None
    finally:
        db.close()


def _mark(trade: dict[str, Any], copied: bool) -> None:
    db = SessionLocal()
    try:
        if db.query(CopyTradeSeen).filter(CopyTradeSeen.event_key == trade["event_key"]).first():
            return
        db.add(
            CopyTradeSeen(
                event_key=trade["event_key"],
                source=trade.get("source") or "",
                filer=trade.get("filer") or "",
                symbol=trade.get("symbol") or "",
                side=trade.get("side") or "",
                disclosure_date=trade.get("disclosure_date") or "",
                copied=copied,
            )
        )
        db.commit()
    finally:
        db.close()


def _run_one_rule(rule: dict[str, Any], *, execute: bool) -> dict[str, Any]:
    filer = rule["filer"]
    budget = float(rule["weekly_budget"])
    max_order = float(rule.get("max_order") or budget)
    side_filter = rule.get("side") or "buy"
    lookback = int(rule.get("lookback_days") or 14)

    try:
        create_book(filer, starting_cash=10_000.0, auto_execute=True)
    except Exception:
        pass

    state = _load_budget(rule["id"], budget)
    remaining = max(0.0, budget - float(state.get("spent") or 0))

    try:
        trades = fetch_watchlist_trades([filer], lookback_days=lookback)
        feed_error = None
    except Exception as exc:
        trades = []
        feed_error = str(exc)[:200]

    candidates = []
    for t in trades:
        s = (t.get("side") or "").lower()
        if side_filter == "both" or s == side_filter:
            if t.get("event_key") and not _seen(str(t["event_key"])):
                candidates.append(t)
    candidates.sort(key=lambda t: str(t.get("disclosure_date") or ""), reverse=True)
    candidates = candidates[:8]

    limits = RiskLimits(
        max_position_percent=10.0,
        max_order_dollars=max_order,
        max_daily_loss_percent=3.0,
        max_trades_per_day=20,
    )
    engine = PaperExecutionEngine(risk_engine=RiskEngine(limits))
    actions: list[dict[str, Any]] = []
    spent_run = 0.0

    if remaining < 25 or not candidates:
        return {
            "rule_id": rule["id"],
            "filer": filer,
            "spent": state.get("spent"),
            "remaining": remaining,
            "actions": [],
            "feed_error": feed_error,
            "note": "no new disclosures or budget empty",
        }

    per = min(max_order, round(remaining / len(candidates), 2))

    for t in candidates:
        if remaining - spent_run < 25:
            break
        notional = min(per, remaining - spent_run, max_order)
        if notional < 25:
            break
        side = (t.get("side") or "buy").lower()
        if side not in ("buy", "sell"):
            continue
        symbol = str(t.get("symbol") or "").upper()
        kwargs = dict(
            symbol=symbol,
            side=side,
            notional=notional,
            strategy_version=f"rule_{rule['id']}",
            signal_meta={"copied_from": filer, "rule_id": rule["id"]},
        )
        result = engine.execute_approved(**kwargs) if execute else engine.propose_and_validate(**kwargs)
        _mark(t, copied=bool(result.get("executed")))
        actions.append(
            {
                "symbol": symbol,
                "side": side,
                "notional": notional,
                "risk_decision": result.get("risk_decision"),
                "executed": result.get("executed"),
                "disclosure_date": t.get("disclosure_date"),
            }
        )
        if result.get("executed") or (not execute and result.get("risk_decision") == "ALLOW"):
            spent_run += notional

    state["spent"] = float(state.get("spent") or 0) + spent_run
    _save_budget(rule["id"], state)
    return {
        "rule_id": rule["id"],
        "filer": filer,
        "budget": budget,
        "spent": state["spent"],
        "remaining": max(0.0, budget - float(state["spent"])),
        "spent_this_run": spent_run,
        "actions": actions,
        "feed_error": feed_error,
    }


def format_allocate_caption(report: dict[str, Any]) -> str:
    lines = [
        "<b>Weekly paper allocate</b>",
        f"Week <code>{report.get('week')}</code> · rules run: {report.get('rules_run', 0)}",
        "",
    ]
    for block in report.get("results") or []:
        lines.append(
            f"<b>{block.get('filer')}</b> "
            f"spent ${float(block.get('spent') or 0):,.0f} / "
            f"${float(block.get('budget') or 0):,.0f}"
        )
        for a in (block.get("actions") or [])[:5]:
            flag = "filled" if a.get("executed") else a.get("risk_decision")
            lines.append(
                f"  • {flag} {(a.get('side') or '').upper()} "
                f"<code>{a.get('symbol')}</code> ${a.get('notional')}"
            )
        if not block.get("actions"):
            lines.append(f"  <i>{block.get('note') or 'no new fills'}</i>")
    lines.append("")
    lines.append("<i>Paper only · delayed public PTRs · not advice · risk on</i>")
    return "\n".join(lines)


def run_all_rules(*, execute: bool = True, notify: bool = True) -> dict[str, Any]:
    init_db()
    rules = [r for r in load_rules() if r.get("enabled")]
    results = []
    for rule in rules:
        try:
            results.append(_run_one_rule(rule, execute=execute))
        except Exception as exc:
            log.warning("rule %s failed: %s", rule.get("id"), type(exc).__name__)
            results.append({"rule_id": rule.get("id"), "filer": rule.get("filer"), "error": str(exc)[:200]})

    report = {
        "week": _iso_week(),
        "rules_run": len(rules),
        "results": results,
        "execute": execute,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "weekly_allocate_latest.json").write_text(json.dumps(report, indent=2, default=str))
    if notify:
        report["telegram"] = send_telegram(format_allocate_caption(report))
    return report


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser()
    p.add_argument("--propose-only", action="store_true")
    p.add_argument("--no-notify", action="store_true")
    args = p.parse_args()
    print(json.dumps(run_all_rules(execute=not args.propose_only, notify=not args.no_notify), indent=2, default=str))


if __name__ == "__main__":
    main()
