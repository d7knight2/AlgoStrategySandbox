"""Long-poll Telegram inbound commands (chat-id allowlist).

Run: python -m src.notifications.bot
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from src.database import init_db
from src.notifications.commands import handle_text
from src.notifications.telegram import send_telegram, telegram_configured, telegram_request

log = logging.getLogger("trading_core.telegram.bot")
OFFSET_PATH = Path(__file__).resolve().parents[2] / "data" / "reports" / "telegram_offset.txt"


def _read_offset() -> int:
    try:
        return int(OFFSET_PATH.read_text().strip() or "0")
    except (OSError, ValueError):
        return 0


def _write_offset(value: int) -> None:
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_PATH.write_text(str(value))


def process_updates() -> int:
    """Fetch and handle one getUpdates batch. Returns number of messages handled."""
    offset = _read_offset()
    data = telegram_request(
        "getUpdates",
        json_body={
            "offset": offset,
            "timeout": 25,
            "allowed_updates": ["message"],
        },
        timeout=35.0,
    )
    if not data.get("ok"):
        log.warning("getUpdates failed: %s", data.get("error") or data.get("description"))
        return 0
    handled = 0
    for upd in data.get("result") or []:
        uid = int(upd.get("update_id") or 0)
        _write_offset(uid + 1)
        msg = upd.get("message") or upd.get("edited_message") or {}
        text = str(msg.get("text") or "")
        chat = msg.get("chat") or {}
        chat_id = str(chat.get("id") or "")
        if not text or not chat_id:
            continue
        reply = handle_text(text, chat_id=chat_id)
        if reply:
            send_telegram(reply)
            handled += 1
    return handled


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    init_db()
    if not telegram_configured():
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")
        raise SystemExit(1)
    log.info("telegram bot poller starting (chat-id allowlist)")
    while True:
        try:
            process_updates()
        except Exception:
            log.exception("poller loop")
            time.sleep(5)


if __name__ == "__main__":
    main()
