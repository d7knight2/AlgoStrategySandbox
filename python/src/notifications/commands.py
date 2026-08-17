"""Inbound Telegram commands (chat-id allowlist). Paper ops only.

No /buy /sell /execute ticker commands. /track creates a virtual paper book
that auto-copies that politician's public PTRs at the $100 cap.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from src.config import settings
from src.copytrade.books import (
    DEFAULT_CASH,
    apply_virtual_fill,
    book_snapshot,
    create_book,
    disable_book,
    list_book_snapshots,
    quote_price,
)
from src.copytrade.engine import filer_watchlist, format_copytrade_digest
from src.database.models import TelegramPref
from src.database.session import SessionLocal
from src.feeds.congress import fetch_watchlist_trades
from src.notifications.telegram import chat_allowed, esc_html

log = logging.getLogger("trading_core.telegram.commands")
REPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"
_LAST_CMD_AT = 0.0
_RATE_S = 1.25

HELP = """<b>Trading Core · Telegram</b>
Paper only · risk engine · delayed public filings

<b>Ask / customize</b>
/help
/status — Alpaca paper account
/positions — open paper positions
/report — daily progress
/report copy — last STOCK Act digest
/report weekly — paper funds vs tracked filers
/prefs — digest short|full, weekly on|off, daily on|off

<b>Government trades</b>
/gov sells [name] [days]
/gov buys [name] [days]
/gov Pelosi 45

<b>Paper books (one per politician)</b>
/track Pelosi — virtual $10k book, auto-copy future PTRs
/track Pelosi 5000 — custom starting cash
/untrack Pelosi
/books
/book Pelosi

No live trading. No /buy or /sell. Copies use a $100 cap, not disclosed size.
"""


def get_prefs() -> TelegramPref:
    db = SessionLocal()
    try:
        row = db.get(TelegramPref, 1)
        if row is None:
            row = TelegramPref(
                id=1,
                digest_mode="full",
                weekly_enabled=True,
                daily_copytrade=True,
                daily_progress=True,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        return row
    finally:
        db.close()


def set_prefs(**kwargs: Any) -> TelegramPref:
    db = SessionLocal()
    try:
        row = db.get(TelegramPref, 1)
        if row is None:
            row = TelegramPref(id=1)
            db.add(row)
        for key, val in kwargs.items():
            if hasattr(row, key) and val is not None:
                setattr(row, key, val)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def nl_to_command(text: str) -> str:
    """Map a plain-language question onto a slash command."""
    t = text.strip()
    lower = t.lower()
    if lower in {"help", "hi", "hello", "start", "?"}:
        return "/help"
    if re.search(r"\buntrack\b", lower):
        rest = re.sub(r"^.*\buntrack\b", "", t, flags=re.I).strip()
        return f"/untrack {rest}".strip()
    if re.search(r"\btrack\b", lower):
        rest = re.sub(r"^.*\btrack\b", "", t, flags=re.I).strip()
        return f"/track {rest}".strip()
    if (
        "weekly" in lower
        or "how am i doing" in lower
        or "how are the paper" in lower
        or "paper fund" in lower
        or ("how good" in lower and "paper" in lower)
    ):
        return "/weekly"
    if "position" in lower or "portfolio" in lower or "holdings" in lower:
        return "/positions"
    if "pref" in lower or "customize" in lower:
        return "/prefs"
    if re.search(r"\bsell", lower) and (
        "gov" in lower or "congress" in lower or "politic" in lower or "pelosi" in lower
    ):
        name = _guess_name(t)
        return f"/gov sells {name}".strip()
    if "government" in lower or lower.startswith("gov "):
        side = "sells" if "sell" in lower else "buys" if "buy" in lower else ""
        name = _guess_name(t)
        return f"/gov {side} {name}".strip()
    if "status" in lower or "health" in lower or "equity" in lower:
        return "/status"
    if "report" in lower:
        return "/report"
    if "book" in lower:
        name = _guess_name(t)
        return f"/book {name}".strip() if name else "/books"
    return t if t.startswith("/") else "/help"


def _guess_name(text: str) -> str:
    for token in (
        "Pelosi",
        "Tuberville",
        "Gottheimer",
        "McCaul",
        "Newhouse",
        "Khanna",
        "Buffett",
        "Ackman",
        "Icahn",
    ):
        if token.lower() in text.lower():
            return token
    return ""


def handle_text(text: str, *, chat_id: str) -> str:
    if not chat_allowed(chat_id):
        log.info("telegram inbound ignored: chat_id not allowlisted")
        return ""
    global _LAST_CMD_AT
    now = time.monotonic()
    if now - _LAST_CMD_AT < _RATE_S:
        return "Slow down a second — still paper-only."
    _LAST_CMD_AT = now

    raw = (text or "").strip()
    if not raw:
        return HELP
    if not raw.startswith("/"):
        raw = nl_to_command(raw)
    cmd, *args = raw.split()
    cmd = cmd.split("@", 1)[0].lower()
    arg = " ".join(args).strip()
    try:
        return _dispatch(cmd, arg)
    except Exception as exc:
        log.warning("command failed cmd=%s type=%s", cmd, type(exc).__name__)
        return f"Could not run <code>{esc_html(cmd)}</code> ({esc_html(type(exc).__name__)})."


def _dispatch(cmd: str, arg: str) -> str:
    if cmd in {"/start", "/help"}:
        return HELP
    if cmd == "/status":
        return _cmd_status()
    if cmd == "/positions":
        return _cmd_positions()
    if cmd in {"/report", "/weekly"}:
        return _cmd_report(arg if cmd == "/report" else "weekly")
    if cmd == "/prefs":
        return _cmd_prefs(arg)
    if cmd == "/gov":
        return _cmd_gov(arg)
    if cmd == "/track":
        return _cmd_track(arg)
    if cmd == "/untrack":
        return _cmd_untrack(arg)
    if cmd == "/books":
        return _cmd_books()
    if cmd == "/book":
        return _cmd_book(arg)
    if cmd == "/pause":
        return _cmd_pause(True)
    if cmd == "/resume":
        return _cmd_pause(False)
    return "Unknown command. /help"


def _cmd_status() -> str:
    from src.broker import AlpacaBroker
    from src.main import risk_engine

    broker = AlpacaBroker()
    acct = broker.get_account()
    market = broker.get_market_status()
    pos = broker.get_positions()
    books = list_book_snapshots(fetch_prices=False)
    live_books = [b for b in books if b.get("enabled")]
    return "\n".join(
        [
            "<b>Paper account</b>",
            f"Equity <code>${float(acct.get('equity') or 0):,.2f}</code>",
            f"Cash <code>${float(acct.get('cash') or 0):,.2f}</code>",
            f"Positions {len(pos)} · filer books {len(live_books)}",
            f"Market {'OPEN' if market.get('is_open') else 'CLOSED'}",
            f"Paused <code>{risk_engine.limits.trading_paused}</code>",
            f"Mode <code>{settings.trading_mode}</code> · live disabled",
        ]
    )


def _cmd_positions() -> str:
    from src.broker import AlpacaBroker

    pos = AlpacaBroker().get_positions()
    lines = ["<b>Alpaca paper positions</b>"]
    if not pos:
        lines.append("None open.")
    else:
        for p in pos[:20]:
            lines.append(
                f"• <code>{esc_html(p.get('symbol'))}</code> qty={p.get('qty')} "
                f"uP/L=${float(p.get('unrealized_pl') or 0):+.2f}"
            )
    books = list_book_snapshots(fetch_prices=True)
    enabled = [b for b in books if b.get("enabled")]
    if enabled:
        lines.append("")
        lines.append("<b>Politician paper books</b>")
        for b in enabled:
            lines.append(
                f"• {esc_html(b['filer'])} equity ${b['equity']:,.2f} "
                f"({b['return_pct']:+.1f}%) · {len(b.get('positions') or [])} names"
            )
    return "\n".join(lines)


def _cmd_report(kind: str) -> str:
    k = (kind or "daily").strip().lower()
    if k in {"weekly", "week", "funds"}:
        from src.reporting.weekly import format_weekly_digest, generate_weekly_report

        return format_weekly_digest(generate_weekly_report(notify=False))
    if k in {"copy", "copytrade", "gov", "digest"}:
        latest = REPORTS_DIR / "copytrade_latest.json"
        if not latest.exists():
            return "No copy-trade digest yet. It runs weekdays 17:00 PT."
        data = json.loads(latest.read_text())
        prefs = get_prefs()
        return format_copytrade_digest(data, style=prefs.digest_mode)
    from src.reporting.progress import generate_progress_report

    report = generate_progress_report(notify_telegram=False)
    summary = esc_html(report.get("summary") or "")
    return f"<b>Progress report</b>\n<pre>{summary[:3200]}</pre>"


def _cmd_prefs(arg: str) -> str:
    parts = arg.lower().split()
    updates: dict[str, Any] = {}
    if "short" in parts:
        updates["digest_mode"] = "short"
    if "full" in parts:
        updates["digest_mode"] = "full"
    if "weekly" in parts and "off" in parts:
        updates["weekly_enabled"] = False
    elif "weekly" in parts and "on" in parts:
        updates["weekly_enabled"] = True
    if "daily" in parts and "off" in parts:
        updates["daily_copytrade"] = False
    elif "daily" in parts and "on" in parts:
        updates["daily_copytrade"] = True
    if "progress" in parts and "off" in parts:
        updates["daily_progress"] = False
    elif "progress" in parts and "on" in parts:
        updates["daily_progress"] = True
    row = set_prefs(**updates) if updates else get_prefs()
    return (
        "<b>Report prefs</b>\n"
        f"Digest: <code>{esc_html(row.digest_mode)}</code> (short|full)\n"
        f"Daily copy-trade: <code>{row.daily_copytrade}</code>\n"
        f"Weekday progress: <code>{row.daily_progress}</code>\n"
        f"Weekly funds recap: <code>{row.weekly_enabled}</code>\n\n"
        "Examples: <code>/prefs digest short</code> · "
        "<code>/prefs weekly off</code> · <code>/prefs daily on</code>"
    )


def _cmd_gov(arg: str) -> str:
    side = None
    days = 45
    name_parts: list[str] = []
    for tok in arg.split():
        low = tok.lower()
        if low in {"sell", "sells", "sold"}:
            side = "sell"
        elif low in {"buy", "buys", "bought", "purchase"}:
            side = "buy"
        elif tok.isdigit():
            days = max(1, min(int(tok), 90))
        else:
            name_parts.append(tok)
    name = " ".join(name_parts).strip()
    watch = [name] if name else filer_watchlist()
    try:
        rows = fetch_watchlist_trades(watch, lookback_days=days)
    except Exception as exc:
        return f"STOCK Act feed unavailable ({esc_html(type(exc).__name__)})."
    if side:
        rows = [r for r in rows if r.get("side") == side]
    label = {"sell": "sells", "buy": "buys"}.get(side or "", "trades")
    who = name or "watchlist"
    lines = [
        f"<b>Public {label}</b> · {esc_html(who)} · {days}d",
        "<i>Delayed PTRs · not advice</i>",
    ]
    if not rows:
        lines.append("None in this window.")
        return "\n".join(lines)
    for r in rows[:15]:
        lines.append(
            f"• {esc_html(r.get('watchlist_match'))} {(r.get('side') or '').upper()} "
            f"<code>{esc_html(r.get('symbol'))}</code> {esc_html(r.get('amount') or '')} "
            f"filed {esc_html(r.get('disclosure_date'))}"
        )
    return "\n".join(lines)


def _cmd_track(arg: str) -> str:
    if not arg:
        return "Usage: <code>/track Nancy Pelosi</code> or <code>/track Pelosi 5000</code>"
    cash = DEFAULT_CASH
    parts = arg.split()
    if parts and re.fullmatch(r"\d+(\.\d+)?", parts[-1]):
        cash = float(parts[-1])
        parts = parts[:-1]
    filer = " ".join(parts).strip()
    created = create_book(filer, starting_cash=cash, auto_execute=True)
    if not created.get("ok"):
        return esc_html(created.get("error") or "could not create book")
    seeded = _seed_and_backfill(created["filer"])
    snap = book_snapshot(created["filer"], fetch_prices=False) or created
    return (
        f"<b>Paper book · {esc_html(created['filer'])}</b>\n"
        f"{'Created' if created.get('created') else 'Updated'} · "
        f"starting ${float(created['starting_cash']):,.0f}\n"
        f"Auto-copy future public PTRs: on (Alpaca paper after RiskEngine, $100 cap)\n"
        f"Virtual backfill: {seeded.get('fills', 0)} lots, "
        f"{seeded.get('seen', 0)} filings marked seen so we do not dump a 45d Alpaca flood.\n"
        f"Cash ${float(snap.get('cash') or created['cash']):,.2f}\n"
        f"/book {esc_html(created['filer'])} · /untrack to stop"
    )


def _seed_and_backfill(filer: str) -> dict[str, int]:
    """Virtual-replay lookback PTRs; mark event_keys seen so Alpaca is future-only."""
    from src.copytrade.engine import _already_seen, _mark_seen

    fills = 0
    seen_n = 0
    try:
        rows = fetch_watchlist_trades([filer], lookback_days=int(settings.copytrade_lookback_days))
    except Exception as exc:
        log.warning("track backfill feed failed: %s", exc)
        return {"fills": 0, "seen": 0}
    db = SessionLocal()
    try:
        for trade in rows:
            px = quote_price(trade["symbol"]) or 0.0
            if px > 0:
                applied = apply_virtual_fill(trade, price=px, via="backfill")
                if any(a.get("ok") and not a.get("skipped") for a in applied):
                    fills += 1
            if not _already_seen(db, trade["event_key"]):
                _mark_seen(db, trade, copied=False)
                seen_n += 1
        db.commit()
    finally:
        db.close()
    return {"fills": fills, "seen": seen_n}


def _cmd_untrack(arg: str) -> str:
    if not arg:
        return "Usage: <code>/untrack Pelosi</code>"
    out = disable_book(arg)
    if not out.get("ok"):
        return esc_html(out.get("error") or "not found")
    return f"Stopped auto-copy for <b>{esc_html(out['filer'])}</b>. Ledger kept for history."


def _cmd_books() -> str:
    snaps = list_book_snapshots(fetch_prices=True)
    if not snaps:
        return "No politician paper books yet. Try <code>/track Pelosi</code>."
    lines = ["<b>Politician paper books</b>"]
    for b in snaps:
        flag = "on" if b.get("enabled") else "off"
        lines.append(
            f"• {esc_html(b['filer'])} [{flag}] ${b['equity']:,.2f} "
            f"({b['return_pct']:+.1f}%) cash ${b['cash']:,.2f}"
        )
    return "\n".join(lines)


def _cmd_book(arg: str) -> str:
    if not arg:
        return _cmd_books()
    snap = book_snapshot(arg, fetch_prices=True)
    if not snap:
        return f"No book matching {esc_html(arg)}. /books"
    lines = [
        f"<b>{esc_html(snap['filer'])} paper book</b>",
        f"Equity ${snap['equity']:,.2f} ({snap['return_pct']:+.1f}% vs start "
        f"${snap['starting_cash']:,.0f})",
        f"Cash ${snap['cash']:,.2f} · auto-copy {'on' if snap['auto_execute'] else 'off'}",
    ]
    for p in (snap.get("positions") or [])[:12]:
        last = p.get("last")
        last_s = f"${last:.2f}" if last else "n/a"
        lines.append(
            f"• <code>{esc_html(p['symbol'])}</code> qty={p['qty']} avg={p['avg_price']} last={last_s}"
        )
    if not snap.get("positions"):
        lines.append("No open virtual lots yet (waiting for a new public buy).")
    return "\n".join(lines)


def _cmd_pause(paused: bool) -> str:
    from src.main import risk_engine

    if paused:
        risk_engine.pause_trading()
        return "<b>Trading paused</b> (paper proposals blocked)."
    risk_engine.resume_trading()
    return "<b>Trading resumed</b> · still paper only."


def should_send_daily_copytrade() -> bool:
    return bool(get_prefs().daily_copytrade)


def should_send_weekly() -> bool:
    return bool(get_prefs().weekly_enabled)


def should_send_progress() -> bool:
    return bool(get_prefs().daily_progress)


def digest_style() -> str:
    mode = get_prefs().digest_mode
    return mode if mode in {"short", "full"} else "full"
