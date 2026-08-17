"""Send weekly report: text + AI insights + charts/photos."""

from __future__ import annotations

import logging
from typing import Any

from src.notifications.photo import send_telegram_photo
from src.notifications.telegram import send_telegram, telegram_configured
from src.reporting.weekly_ai import attach_weekly_ai, format_weekly_ai_block

log = logging.getLogger("trading_core.reporting.weekly_notify")


def send_weekly_package(report: dict[str, Any], *, body_html: str) -> dict[str, Any]:
    """Enrich with AI (if quota), send text, then leaderboard + optional AI image."""
    out: dict[str, Any] = {"telegram_configured": telegram_configured()}
    if not telegram_configured():
        return {**out, "sent": False, "reason": "not configured"}

    try:
        attach_weekly_ai(report)
    except Exception as exc:
        log.warning("weekly AI attach failed: %s", type(exc).__name__)
        report["ai_summary"] = {"ok": False, "error": type(exc).__name__}

    ai_block = format_weekly_ai_block(report)
    full = body_html + ai_block
    # Telegram caption/text limits
    if len(full) > 3900:
        full = full[:3900] + "…"

    out["text"] = send_telegram(full)

    # Deterministic leaderboard chart (always preferred for numbers)
    try:
        from src.notifications.leaderboard_notify import send_leaderboard_update

        out["leaderboard"] = send_leaderboard_update(fetch_prices=True, weekly=True)
    except Exception as exc:
        log.warning("weekly leaderboard photo failed: %s", type(exc).__name__)
        out["leaderboard"] = {"sent": False, "error": type(exc).__name__}

    # Optional AI image (decorative)
    ai_img = report.get("ai_image") or {}
    if ai_img.get("ok") and ai_img.get("path"):
        cap = (
            "<b>Weekly visual</b> (AI)\n"
            "<i>Paper research mood image · not a chart of real P&L</i>"
        )
        out["ai_photo"] = send_telegram_photo(ai_img["path"], caption=cap)
    else:
        out["ai_photo"] = {"sent": False, "reason": ai_img.get("error") or "skipped"}

    out["sent"] = bool((out.get("text") or {}).get("sent"))
    out["ai_summary_ok"] = bool((report.get("ai_summary") or {}).get("ok"))
    return out
