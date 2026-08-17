"""Weekly $1,000 paper allocation copying Nancy Pelosi public PTRs.

Paper only. Direction from delayed STOCK Act filings — not her real size.
Orders still pass RiskEngine (strategy-local limits allow up to $1k/order).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.copytrade.books import create_book
from src.database import init_db
from src.database.models import CopyTradeSeen
from src.database.session import SessionLocal
from src.execution import PaperExecutionEngine
from src.feeds.congress import fetch_watchlist_trades
from src.notifications import send_telegram
from src.risk import RiskEngine, RiskLimits

log = logging.getLogger("trading_core.copytrade.weekly_pelosi")
REPORTS = Path(__file__).resolve().parents[2] / "data" / "reports"
BUDGET_PATH = REPORTS / "pelosi_weekly_budget.json"

FILER = "Nancy Pelosi"
WEEKLY_BUDGET = 1_000.0
LOOKBACK_DAYS = 14
# Strategy-local risk: allow the $1k weekly slice; still hard-capped and paper-only.
STRATEGY_LIMITS = RiskLimits(
    max_position_percent=10.0,
    max_order_dollars=1_000.0,
    max_daily_loss_percent=3.0,
    max_trades_per_day=15,
)


def _iso_week(dt: datetime | None = None) -> str:
    d = dt or datetime.utcnow()
    return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"


def _load_budget() -> dict[str, Any]:
    week = _iso_week()
    if BUDGET_PATH.is_file():
        try:
            data = json.loads(BUDGET_PATH.read_text())
            if data.get("week") == week:
                return data
        except Exception:
            pass
    return {"week": week, "budget": WEEKLY_BUDGET, "spent": 0.0, "fills": []}


def _save_budget(data: dict[str, Any]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    BUDGET_PATH.write_text(json.dumps(data, indent=2, default=str))


def _already_seen(event_key: str) -> bool:
    db = SessionLocal()
    try:
        return (
            db.query(CopyTradeSeen).filter(CopyTradeSeen.event_key == event_key).first() is not None
        )
    finally:
        db.close()


def _mark_seen(trade: dict[str, Any], copied: bool) -> None:
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


def format_pelosi_caption(report: dict[str, Any]) -> str:
    lines = [
        "<b>Weekly Pelosi paper allocate</b>",
        f"Budget: <code>${report.get('budget'):,.0f}</code> · "
        f"spent <code>${report.get('spent'):,.0f}</code> · "
        f"left <code>${report.get('remaining'):,.0f}</code>",
        f"Week: <code>{report.get('week')}</code>",
        "",
    ]
    actions = report.get("actions") or []
    if not actions:
        lines.append("No new public PTR buys to copy this window.")
    for a in actions[:10]:
        flag = "filled" if a.get("executed") else (a.get("risk_decision") or "skip")
        lines.append(
            f"• {flag} {(a.get('side') or '').upper()} "
            f"<code>{a.get('symbol')}</code> ${a.get('notional')} "
            f"filed {a.get('disclosure_date') or '—'}"
        )
        if a.get("risk_reasons"):
            lines.append(f"  <i>{a.get('risk_reasons')}</i>")
    lines.append("")
    lines.append(
        "<i>Paper only · delayed public PTRs · not her real size · not advice · risk engine on</i>"
    )
    return "\n".join(lines)


def run_weekly_pelosi(
    *,
    execute: bool = True,
    notify: bool = True,
    weekly_budget: float = WEEKLY_BUDGET,
    lookback_days: int = LOOKBACK_DAYS,
) -> dict[str, Any]:
    """Spend up to weekly_budget on new Nancy Pelosi BUY disclosures (paper)."""
    init_db()
    try:
        create_book(FILER, starting_cash=10_000.0, auto_execute=True)
    except Exception:
        pass

    budget_state = _load_budget()
    budget_state["budget"] = float(weekly_budget)
    remaining = max(0.0, float(weekly_budget) - float(budget_state.get("spent") or 0))

    try:
        trades = fetch_watchlist_trades([FILER], lookback_days=lookback_days)
        feed_error = None
    except Exception as exc:
        trades = []
        feed_error = str(exc)[:300]

    # Prefer buys; only process unseen event keys
    buys = [
        t
        for t in trades
        if (t.get("side") or "").lower() == "buy"
        and t.get("event_key")
        and not _already_seen(str(t["event_key"]))
    ]
    # Newest disclosure first
    buys.sort(key=lambda t: str(t.get("disclosure_date") or ""), reverse=True)

    risk = RiskEngine(STRATEGY_LIMITS)
    engine = PaperExecutionEngine(risk_engine=risk)
    actions: list[dict[str, Any]] = []
    spent_this_run = 0.0

    if remaining <= 1.0:
        report = {
            "week": budget_state["week"],
            "budget": weekly_budget,
            "spent": budget_state.get("spent"),
            "remaining": remaining,
            "actions": [],
            "note": "Weekly $1,000 paper budget already used",
            "feed_error": feed_error,
        }
        if notify:
            report["telegram"] = send_telegram(format_pelosi_caption(report))
        return report

    # Equal-weight the new buys against remaining budget (cap count)
    slice_buys = buys[:8]
    n = len(slice_buys) or 1
    per = round(remaining / n, 2) if slice_buys else 0.0
    per = min(per, float(STRATEGY_LIMITS.max_order_dollars))

    for t in slice_buys:
        if remaining - spent_this_run < 25:
            break
        notional = min(per, remaining - spent_this_run)
        if notional < 25:
            break
        symbol = str(t.get("symbol") or "").upper()
        result = engine.execute_approved(
            symbol=symbol,
            side="buy",
            notional=notional,
            strategy_version="pelosi_weekly_v1",
            signal_meta={
                "copied_from": FILER,
                "disclosure_date": t.get("disclosure_date"),
                "source": t.get("source"),
            },
        ) if execute else engine.propose_and_validate(
            symbol=symbol,
            side="buy",
            notional=notional,
            strategy_version="pelosi_weekly_v1",
            signal_meta={"copied_from": FILER},
        )

        copied = bool(result.get("executed") or result.get("risk_decision") == "ALLOW")
        _mark_seen(t, copied=bool(result.get("executed")))
        row = {
            "symbol": symbol,
            "side": "buy",
            "notional": notional,
            "disclosure_date": t.get("disclosure_date"),
            "risk_decision": result.get("risk_decision"),
            "risk_reasons": "; ".join(result.get("risk_reasons") or [])
            if isinstance(result.get("risk_reasons"), list)
            else result.get("risk_reasons"),
            "executed": result.get("executed"),
            "copied_from": FILER,
        }
        actions.append(row)
        if result.get("executed") or (
            not execute and result.get("risk_decision") == "ALLOW"
        ):
            spent_this_run += notional
            budget_state.setdefault("fills", []).append(
                {
                    "symbol": symbol,
                    "notional": notional,
                    "at": datetime.utcnow().isoformat() + "Z",
                    "executed": bool(result.get("executed")),
                }
            )

    budget_state["spent"] = float(budget_state.get("spent") or 0) + spent_this_run
    _save_budget(budget_state)

    report: dict[str, Any] = {
        "week": budget_state["week"],
        "budget": weekly_budget,
        "spent": budget_state["spent"],
        "remaining": max(0.0, weekly_budget - float(budget_state["spent"])),
        "spent_this_run": spent_this_run,
        "new_buys_seen": len(slice_buys),
        "actions": actions,
        "execute": execute,
        "feed_error": feed_error,
        "mode": "paper",
        "notes": [
            "Copies direction only from public delayed PTRs",
            f"Weekly paper budget ${weekly_budget:,.0f}",
            "Live trading disabled",
        ],
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "pelosi_weekly_latest.json").write_text(
        json.dumps(report, indent=2, default=str)
    )

    if notify:
        report["telegram"] = send_telegram(format_pelosi_caption(report))
    return report


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(description="Weekly Nancy Pelosi $1k paper allocate")
    p.add_argument("--propose-only", action="store_true")
    p.add_argument("--no-notify", action="store_true")
    p.add_argument("--budget", type=float, default=WEEKLY_BUDGET)
    args = p.parse_args()
    report = run_weekly_pelosi(
        execute=not args.propose_only,
        notify=not args.no_notify,
        weekly_budget=args.budget,
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
