"""Paper copy-trade of public STOCK Act / 13F disclosures.

Never live. Every order still goes through RiskEngine. Sizing is capped
(COPYTRADE_MAX_NOTIONAL) — we copy *direction*, not disclosed dollar size.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import settings
from src.database import init_db
from src.database.models import CopyTradeSeen, ShadowHolding, SystemEvent
from src.database.session import SessionLocal
from src.execution import PaperExecutionEngine
from src.feeds.congress import fetch_watchlist_trades
from src.feeds.sec13f import fetch_manager_filings
from src.feeds.sentiment import fetch_fear_greed
from src.notifications import send_telegram
from src.risk import RiskEngine, RiskLimits

log = logging.getLogger("trading_core.copytrade")
REPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"


def filer_watchlist() -> list[str]:
    raw = getattr(settings, "copytrade_filers", "") or ""
    return [p.strip() for p in raw.split(",") if p.strip()]


def _already_seen(db, event_key: str) -> bool:
    return db.query(CopyTradeSeen).filter(CopyTradeSeen.event_key == event_key).first() is not None


def _mark_seen(db, trade: dict[str, Any], copied: bool) -> None:
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


def _upsert_shadow(db, trade: dict[str, Any]) -> None:
    owner = trade.get("watchlist_match") or trade.get("filer") or ""
    symbol = trade["symbol"]
    row = (
        db.query(ShadowHolding)
        .filter(ShadowHolding.owner_key == owner, ShadowHolding.symbol == symbol)
        .first()
    )
    if row is None:
        row = ShadowHolding(owner_key=owner, symbol=symbol)
        db.add(row)
    row.side = trade["side"]
    row.source = trade.get("source") or ""
    row.amount = trade.get("amount") or ""
    row.disclosure_date = trade.get("disclosure_date") or ""
    row.updated_at = datetime.utcnow()


def format_copytrade_digest(report: dict[str, Any]) -> str:
    def esc(text: Any) -> str:
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    fng = report.get("sentiment") or {}
    lines = [
        "<b>Trading Core · daily copy-trade digest</b>",
        f"Mode: <code>{esc(report.get('mode'))}</code> · paper only",
        f"Lookback: {report.get('lookback_days')}d disclosures",
    ]
    if fng.get("ok"):
        lines.append(f"Fear &amp; Greed: <code>{fng.get('value')}</code> {esc(fng.get('label'))}")
    elif fng.get("error"):
        lines.append(f"Fear &amp; Greed: unavailable ({esc(fng.get('error'))[:80]})")

    new_trades = report.get("new_disclosures") or []
    lines.append("")
    lines.append(f"<b>New STOCK Act filings on watchlist</b> ({len(new_trades)})")
    if not new_trades:
        lines.append("None this window.")
    else:
        for t in new_trades[:12]:
            lines.append(
                f"• {esc(t.get('watchlist_match'))} "
                f"{(t.get('side') or '').upper()} <code>{esc(t.get('symbol'))}</code> "
                f"{esc(t.get('amount') or '')} "
                f"filed {esc(t.get('disclosure_date'))}"
            )

    actions = report.get("actions") or []
    allow = [a for a in actions if a.get("risk_decision") == "ALLOW"]
    copied = [a for a in actions if a.get("executed")]
    lines.append("")
    lines.append(
        f"<b>Paper copies</b> ALLOW={len(allow)} executed={len(copied)} "
        f"(cap ${report.get('max_notional')})"
    )
    for a in allow[:8]:
        flag = "filled" if a.get("executed") else "proposed"
        lines.append(
            f"• {flag} {(a.get('side') or '').upper()} <code>{esc(a.get('symbol'))}</code> "
            f"${a.get('notional')} ← {esc(a.get('copied_from') or '')}"
        )

    shadows = report.get("shadow_vs_paper") or []
    lines.append("")
    lines.append("<b>Paper vs tracked filers</b>")
    if not shadows:
        lines.append("No overlapping symbols yet.")
    else:
        for s in shadows[:12]:
            lines.append(
                f"• <code>{esc(s['symbol'])}</code> "
                f"paper={esc(s.get('paper_qty', '—'))} "
                f"shadow={esc(s.get('owner'))} {(s.get('shadow_side') or '').upper()}"
            )

    filings = report.get("investor_13f") or []
    if filings:
        lines.append("")
        lines.append("<b>Famous-investor 13F (delayed)</b>")
        for f in filings:
            if f.get("ok"):
                lines.append(
                    f"• {esc(f.get('manager') or f.get('name'))} "
                    f"{esc(f.get('form'))} filed {esc(f.get('filed'))}"
                )
            else:
                lines.append(f"• {esc(f.get('name'))}: {esc(f.get('error') or 'unavailable')}")

    lines.append("")
    lines.append(
        "<i>Public delayed filings · not advice · live trading disabled · risk engine active</i>"
    )
    return "\n".join(lines)


def _paper_overlap(shadows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        from src.broker import AlpacaBroker

        positions = AlpacaBroker().get_positions()
    except Exception as exc:
        log.warning("paper positions unavailable: %s", exc)
        return []
    by_sym = {str(p.get("symbol") or "").upper(): p for p in positions}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sh in shadows:
        sym = sh["symbol"]
        if sym in seen:
            continue
        pos = by_sym.get(sym)
        if not pos:
            continue
        seen.add(sym)
        out.append(
            {
                "symbol": sym,
                "paper_qty": pos.get("qty"),
                "paper_pl": pos.get("unrealized_pl"),
                "owner": sh.get("owner_key"),
                "shadow_side": sh.get("side"),
            }
        )
    return out


def run_copytrade_daily(
    *,
    execute: bool | None = None,
    notify: bool = True,
    lookback_days: int | None = None,
    max_notional: float | None = None,
) -> dict[str, Any]:
    init_db()
    do_execute = settings.copytrade_execute_paper if execute is None else execute
    lookback = lookback_days if lookback_days is not None else int(settings.copytrade_lookback_days)
    notional = float(max_notional if max_notional is not None else settings.copytrade_max_notional)
    watch = filer_watchlist()

    sentiment = fetch_fear_greed()
    try:
        disclosures = fetch_watchlist_trades(watch, lookback_days=lookback)
        feed_error = None
    except Exception as exc:
        log.warning("congress feed failed: %s", exc)
        disclosures = []
        feed_error = str(exc)[:300]

    investor_13f = fetch_manager_filings()

    risk = RiskEngine(RiskLimits(max_order_dollars=notional))
    engine = PaperExecutionEngine(risk_engine=risk)

    new_rows: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    shadows: list[dict[str, Any]] = []
    db = SessionLocal()
    try:
        for trade in disclosures:
            if _already_seen(db, trade["event_key"]):
                continue
            new_rows.append(trade)
            _upsert_shadow(db, trade)
            try:
                if do_execute:
                    result = engine.execute_approved(
                        symbol=trade["symbol"],
                        side=trade["side"],
                        notional=notional,
                        strategy_version="copytrade_ptr_v001",
                        signal_meta={
                            "decision": trade["side"].upper(),
                            "signal_score": 0.5,
                            "confidence": 0.5,
                            "components": {"source": trade["source"]},
                        },
                    )
                else:
                    result = engine.propose_and_validate(
                        symbol=trade["symbol"],
                        side=trade["side"],
                        notional=notional,
                        strategy_version="copytrade_ptr_v001",
                        signal_meta={
                            "decision": trade["side"].upper(),
                            "signal_score": 0.5,
                            "confidence": 0.5,
                            "components": {"source": trade["source"]},
                        },
                    )
                result["copied_from"] = trade.get("watchlist_match")
                result["disclosure_date"] = trade.get("disclosure_date")
                actions.append(result)
                copied = bool(result.get("executed"))
            except Exception as exc:
                log.warning("copytrade action failed %s: %s", trade.get("event_key"), exc)
                actions.append(
                    {
                        "symbol": trade["symbol"],
                        "side": trade["side"],
                        "error": str(exc)[:300],
                        "copied_from": trade.get("watchlist_match"),
                    }
                )
                copied = False
            _mark_seen(db, trade, copied=copied)

        shadows = [
            {
                "owner_key": s.owner_key,
                "symbol": s.symbol,
                "side": s.side,
                "amount": s.amount,
                "disclosure_date": s.disclosure_date,
            }
            for s in db.query(ShadowHolding).order_by(ShadowHolding.updated_at.desc()).limit(50)
        ]
        db.add(
            SystemEvent(
                event_type="copytrade_daily",
                message=json.dumps(
                    {
                        "new": len(new_rows),
                        "actions": len(actions),
                        "execute": do_execute,
                    }
                ),
            )
        )
        db.commit()
    finally:
        db.close()

    overlap = _paper_overlap(shadows)
    report: dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "mode": "execute_paper" if do_execute else "propose_only",
        "lookback_days": lookback,
        "max_notional": notional,
        "watchlist": watch,
        "new_disclosures": new_rows,
        "actions": actions,
        "shadow_vs_paper": overlap,
        "sentiment": sentiment,
        "investor_13f": investor_13f,
        "feed_error": feed_error,
        "notes": [
            "STOCK Act and 13F filings are public and delayed.",
            "Paper copies use a fixed notional cap, not the disclosed dollar range.",
            "Live trading is disabled.",
        ],
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    latest = REPORTS_DIR / "copytrade_latest.json"
    latest.write_text(json.dumps(report, indent=2, default=str))
    report["path"] = str(latest)

    if notify:
        try:
            report["telegram"] = send_telegram(format_copytrade_digest(report))
        except Exception as exc:
            report["telegram"] = {"sent": False, "error": str(exc)}

    return report
