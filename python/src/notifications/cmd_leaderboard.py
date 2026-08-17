"""/leaderboard command body (imported by commands.py)."""

from __future__ import annotations

from src.notifications.leaderboard_notify import send_leaderboard_update
from src.notifications.telegram import esc_html


def cmd_leaderboard() -> str:
    result = send_leaderboard_update(fetch_prices=True, weekly=False)
    if result.get("sent"):
        return (
            "<b>Leaderboard sent</b>\n"
            f"books: <code>{result.get('count', 0)}</code>\n"
            "<i>Chart image above · paper only</i>"
        )
    err = (result.get("photo") or {}).get("error") or result.get("reason") or "send failed"
    return f"<b>Leaderboard failed</b>\n<code>{esc_html(err)}</code>"
