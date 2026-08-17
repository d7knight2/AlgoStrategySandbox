"""Telegram Bot alerts (paper trading notifications).

Env:
  TELEGRAM_BOT_TOKEN  — from @BotFather
  TELEGRAM_CHAT_ID    — your chat or group id
"""

from __future__ import annotations

from typing import Any

import httpx

from src.config import settings

TELEGRAM_API = "https://api.telegram.org"


def telegram_configured() -> bool:
    return bool(
        getattr(settings, "telegram_bot_token", "")
        and getattr(settings, "telegram_chat_id", "")
    )


def send_telegram(text: str, *, parse_mode: str | None = "HTML") -> dict[str, Any]:
    """Send a message to the configured chat. No-op if not configured."""
    token = getattr(settings, "telegram_bot_token", "") or ""
    chat_id = getattr(settings, "telegram_chat_id", "") or ""
    if not token or not chat_id:
        return {"sent": False, "reason": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"}

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text[:4000],
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(url, json=payload)
            data = r.json() if r.content else {}
            if r.status_code != 200 or not data.get("ok"):
                return {
                    "sent": False,
                    "status_code": r.status_code,
                    "error": data.get("description") or r.text[:300],
                }
            return {"sent": True, "message_id": data.get("result", {}).get("message_id")}
    except Exception as e:
        return {"sent": False, "error": str(e)}


def format_scan_alert(report: dict[str, Any]) -> str:
    """Human-readable Telegram body for a research scan result."""
    actions = report.get("actions") or []
    signals = report.get("signals") or []
    allow = [a for a in actions if a.get("risk_decision") == "ALLOW"]
    reject = [a for a in actions if a.get("risk_decision") == "REJECT"]

    lines = [
        "<b>Trading Core · signal scan</b>",
        f"Mode: <code>{report.get('mode', 'propose_only')}</code>",
        f"Equity: <code>{report.get('account_equity', '—')}</code>",
        f"Market open: <code>{report.get('market_open')}</code>",
        f"Symbols scored: {len(signals)}",
        f"Proposals: {len(actions)} (ALLOW={len(allow)}, REJECT={len(reject)})",
    ]

    if allow:
        lines.append("")
        lines.append("<b>ALLOW (would trade under risk limits)</b>")
        for a in allow[:8]:
            lines.append(
                f"• {(a.get('side') or '').upper()} <code>{a.get('symbol')}</code> "
                f"notional={a.get('notional')}"
            )
    elif actions:
        lines.append("")
        lines.append("No ALLOW this pass — risk gate held or signals weak.")
    else:
        lines.append("")
        lines.append("No actionable signals.")

    lines.append("")
    lines.append("<i>Paper only · risk engine active</i>")
    return "\n".join(lines)
