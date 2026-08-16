"""Progress reports + optional email delivery."""

from __future__ import annotations

import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from src.broker import AlpacaBroker
from src.config import settings
from src.database.models import AccountSnapshot, SignalRecord, SystemEvent, TradeFill, TradeProposal
from src.database.session import SessionLocal

REPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"


def generate_progress_report() -> dict[str, Any]:
    """Build a human-readable progress snapshot from account + audit DB."""
    broker = AlpacaBroker()
    account = broker.get_account()
    positions = broker.get_positions()
    market = broker.get_market_status()

    since = datetime.utcnow() - timedelta(hours=24)
    db = SessionLocal()
    try:
        proposals = db.query(TradeProposal).filter(TradeProposal.created_at >= since).all()
        fills = db.query(TradeFill).filter(TradeFill.created_at >= since).all()
        signals = db.query(SignalRecord).filter(SignalRecord.created_at >= since).count()
        snaps = db.query(AccountSnapshot).order_by(AccountSnapshot.created_at.desc()).limit(2).all()
    finally:
        db.close()

    allowed = sum(1 for p in proposals if p.risk_decision == "ALLOW")
    rejected = sum(1 for p in proposals if p.risk_decision == "REJECT")
    executed = sum(1 for p in proposals if p.executed)

    equity_change = None
    if len(snaps) >= 2:
        equity_change = snaps[0].equity - snaps[-1].equity

    lines = [
        f"Trading Core progress report — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        f"Mode: {settings.trading_mode} | Market: {'OPEN' if market.get('is_open') else 'CLOSED'}",
        f"Equity: ${float(account.get('equity', 0)):.2f}",
        f"Cash: ${float(account.get('cash', 0)):.2f}",
        f"Buying power: ${float(account.get('buying_power', 0)):.2f}",
        f"Open positions: {len(positions)}",
    ]
    if equity_change is not None:
        lines.append(f"Equity Δ (recent snapshots): ${equity_change:+.2f}")

    lines += [
        "",
        "Last 24h:",
        f"  Signals recorded: {signals}",
        f"  Proposals: {len(proposals)} (ALLOW={allowed}, REJECT={rejected}, executed={executed})",
        f"  Fills: {len(fills)}",
    ]

    if positions:
        lines.append("")
        lines.append("Positions:")
        for p in positions:
            lines.append(
                f"  {p['symbol']}: qty={p['qty']}  value=${float(p['market_value']):.2f}  "
                f"uP/L=${float(p['unrealized_pl']):.2f}"
            )

    if fills:
        lines.append("")
        lines.append("Recent fills:")
        for f in fills[-10:]:
            lines.append(
                f"  {f.created_at} {f.side.upper()} {f.symbol} qty={f.qty} "
                f"order={f.order_id or '-'}"
            )

    lines.append("")
    lines.append("Safety: live trading disabled · risk engine active")
    summary = "\n".join(lines)

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": summary,
        "account": account,
        "positions": positions,
        "stats_24h": {
            "signals": signals,
            "proposals": len(proposals),
            "allow": allowed,
            "reject": rejected,
            "executed": executed,
            "fills": len(fills),
        },
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    latest = REPORTS_DIR / "latest.json"
    latest.write_text(json.dumps(report, indent=2, default=str))

    # audit
    db = SessionLocal()
    try:
        db.add(SystemEvent(event_type="progress_report", message=f"saved {path.name}"))
        db.commit()
    finally:
        db.close()

    report["path"] = str(path)
    return report


def send_report_email(report: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send the progress report via SMTP if configured.

    Env / settings:
      REPORT_EMAIL_TO
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
    """
    to_addr = getattr(settings, "report_email_to", "") or ""
    host = getattr(settings, "smtp_host", "") or ""
    if not to_addr or not host:
        return {
            "email_sent": False,
            "reason": "REPORT_EMAIL_TO or SMTP_HOST not configured",
        }

    if report is None:
        report = generate_progress_report()

    port = int(getattr(settings, "smtp_port", 587) or 587)
    user = getattr(settings, "smtp_user", "") or ""
    password = getattr(settings, "smtp_password", "") or ""
    from_addr = getattr(settings, "smtp_from", "") or user or "trading-core@localhost"

    msg = MIMEText(report.get("summary", "(empty report)"), "plain", "utf-8")
    msg["Subject"] = f"[Trading Core] Progress {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
    msg["From"] = from_addr
    msg["To"] = to_addr

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
            except Exception:
                pass
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(from_addr, [to_addr], msg.as_string())
        return {"email_sent": True, "to": to_addr}
    except Exception as e:
        return {"email_sent": False, "error": str(e)}
