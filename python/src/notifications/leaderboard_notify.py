"""Send leaderboard text + PNG via Telegram (on-demand and weekly)."""

from __future__ import annotations

import logging
from typing import Any

from src.copytrade.leaderboard_image import build_and_save_leaderboard_image
from src.notifications.photo import send_telegram_photo
from src.notifications.telegram import esc_html, send_telegram, telegram_configured

log = logging.getLogger("trading_core.telegram.leaderboard")


def format_leaderboard_caption(board: dict[str, Any], *, limit: int = 8) -> str:
    rows = board.get("leaderboard") or []
    lines = [
        "<b>Paper books leaderboard</b>",
        f"Tracked: <code>{board.get('count', len(rows))}</code>",
        "",
    ]
    if not rows:
        lines.append("No books yet — <code>/track Pelosi</code>")
    else:
        for r in rows[:limit]:
            ret = r.get("return_pct")
            ret_s = f"{float(ret):+.1f}%" if ret is not None else "—"
            eq = r.get("equity")
            eq_s = f"${float(eq):,.0f}" if eq is not None else "—"
            lines.append(
                f"{r.get('rank')}. <b>{esc_html(r.get('filer'))}</b> "
                f"{esc_html(ret_s)} · {esc_html(eq_s)}"
            )
    lines.append("")
    lines.append("<i>Virtual paper · delayed PTRs · not real P&L</i>")
    return "\n".join(lines)


def send_leaderboard_update(*, fetch_prices: bool = True, weekly: bool = False) -> dict[str, Any]:
    """Build PNG + caption and send to the configured chat."""
    if not telegram_configured():
        return {"sent": False, "reason": "telegram not configured"}

    path, board = build_and_save_leaderboard_image(fetch_prices=fetch_prices)
    caption = format_leaderboard_caption(board)
    if weekly:
        caption = "<b>Weekly update</b>\n" + caption

    photo = send_telegram_photo(path, caption=caption, parse_mode="HTML")
    if photo.get("sent"):
        return {"sent": True, "photo": photo, "path": str(path), "count": board.get("count")}

    text = send_telegram(caption)
    return {
        "sent": bool(text.get("sent")),
        "photo": photo,
        "text_fallback": text,
        "path": str(path),
        "count": board.get("count"),
    }
