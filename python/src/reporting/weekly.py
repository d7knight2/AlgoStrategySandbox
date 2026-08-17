"""Weekly recap of Alpaca paper funds and politician paper books."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.broker import AlpacaBroker
from src.copytrade.books import list_book_snapshots
from src.database.models import AccountSnapshot, CopyTradeSeen, FilerBookFill, TelegramPref
from src.database.session import SessionLocal
from src.notifications import send_telegram
from src.notifications.telegram import esc_html

log = logging.getLogger("trading_core.reporting.weekly")
REPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"


def generate_weekly_report(*, notify: bool = True) -> dict[str, Any]:
    broker = AlpacaBroker()
    try:
        account = broker.get_account()
        positions = broker.get_positions()
    except Exception as exc:
        account = {"error": str(exc)[:200]}
        positions = []

    since = datetime.utcnow() - timedelta(days=7)
    db = SessionLocal()
    try:
        snaps = (
            db.query(AccountSnapshot)
            .filter(AccountSnapshot.created_at >= since)
            .order_by(AccountSnapshot.created_at.asc())
            .all()
        )
        older = (
            db.query(AccountSnapshot)
            .filter(AccountSnapshot.created_at < since)
            .order_by(AccountSnapshot.created_at.desc())
            .first()
        )
        fills = db.query(FilerBookFill).filter(FilerBookFill.created_at >= since).all()
        seen = db.query(CopyTradeSeen).filter(CopyTradeSeen.created_at >= since).all()
        pref = db.get(TelegramPref, 1)
        weekly_on = True if pref is None else bool(pref.weekly_enabled)
    finally:
        db.close()

    equity = float(account.get("equity") or 0)
    start_eq = None
    if snaps:
        start_eq = float(snaps[0].equity)
    elif older is not None:
        start_eq = float(older.equity)
    week_pct = None
    if start_eq and start_eq > 0:
        week_pct = round((equity / start_eq - 1.0) * 100.0, 2)

    books = list_book_snapshots(fetch_prices=True)
    buys = sum(1 for s in seen if s.side == "buy")
    sells = sum(1 for s in seen if s.side == "sell")
    copied = sum(1 for s in seen if s.copied)

    report: dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "account": account,
        "positions": positions,
        "week_return_pct": week_pct,
        "week_start_equity": start_eq,
        "books": books,
        "ptr_week": {"buys": buys, "sells": sells, "copied": copied, "fills": len(fills)},
        "unrealized_pl": sum(float(p.get("unrealized_pl") or 0) for p in positions),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    latest = REPORTS_DIR / "weekly_latest.json"
    latest.write_text(json.dumps(report, indent=2, default=str))
    report["path"] = str(latest)

    if notify and weekly_on:
        try:
            report["telegram"] = send_telegram(format_weekly_digest(report))
        except Exception as exc:
            report["telegram"] = {"sent": False, "error": str(exc)}
    elif notify:
        report["telegram"] = {"sent": False, "reason": "weekly pref off"}
    return report


def format_weekly_digest(report: dict[str, Any]) -> str:
    acct = report.get("account") or {}
    equity = float(acct.get("equity") or 0)
    week = report.get("week_return_pct")
    week_s = f"{week:+.2f}%" if week is not None else "n/a"
    ptr = report.get("ptr_week") or {}
    lines = [
        "<b>Trading Core · weekly paper funds</b>",
        f"Alpaca equity <code>${equity:,.2f}</code> · 7d {esc_html(week_s)}",
        f"Open P/L <code>${float(report.get('unrealized_pl') or 0):+.2f}</code> · "
        f"{len(report.get('positions') or [])} positions",
        f"PTRs this week: {ptr.get('buys', 0)} buys / {ptr.get('sells', 0)} sells · "
        f"copied {ptr.get('copied', 0)}",
    ]
    books = [b for b in (report.get("books") or []) if b.get("enabled")]
    lines.append("")
    lines.append("<b>Politician paper books</b>")
    if not books:
        lines.append("None yet. Telegram <code>/track Pelosi</code> to start one.")
    else:
        ranked = sorted(books, key=lambda b: float(b.get("return_pct") or 0), reverse=True)
        for b in ranked:
            lines.append(
                f"• {esc_html(b.get('filer'))} ${float(b.get('equity') or 0):,.2f} "
                f"({float(b.get('return_pct') or 0):+.1f}%) · "
                f"{len(b.get('positions') or [])} names"
            )
    lines.append("")
    lines.append("<i>Paper only · delayed public filings · not advice</i>")
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from src.database import init_db

    init_db()
    report = generate_weekly_report(notify=True)
    print(json.dumps({k: report[k] for k in report if k != "account"}, indent=2, default=str))


if __name__ == "__main__":
    main()
