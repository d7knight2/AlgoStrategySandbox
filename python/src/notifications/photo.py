"""Telegram sendPhoto helper (multipart)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from src.config import settings
from src.notifications.telegram import TELEGRAM_API, _throttle, telegram_configured

log = logging.getLogger("trading_core.telegram.photo")


def send_telegram_photo(
    image_path: str | Path,
    *,
    caption: str | None = None,
    parse_mode: str | None = "HTML",
) -> dict[str, Any]:
    """Send a local image via sendPhoto. Never logs the bot token URL."""
    if not telegram_configured():
        return {"sent": False, "reason": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"}

    token = getattr(settings, "telegram_bot_token", "") or ""
    chat_id = getattr(settings, "telegram_chat_id", "") or ""
    path = Path(image_path)
    if not path.is_file():
        return {"sent": False, "error": f"missing image: {path}"}

    url = f"{TELEGRAM_API}/bot{token}/sendPhoto"
    data: dict[str, Any] = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption[:1024]
        if parse_mode:
            data["parse_mode"] = parse_mode

    try:
        _throttle()
        with path.open("rb") as fh:
            files = {"photo": (path.name, fh, "image/png")}
            with httpx.Client(timeout=60.0) as client:
                r = client.post(url, data=data, files=files)
        payload = r.json() if r.content else {}
        if r.status_code != 200 or not payload.get("ok"):
            err = payload.get("description") or r.text[:300]
            log.warning("telegram photo failed status=%s error=%s", r.status_code, err)
            return {"sent": False, "status_code": r.status_code, "error": err}
        mid = (payload.get("result") or {}).get("message_id")
        log.info("telegram photo ok message_id=%s", mid)
        return {"sent": True, "message_id": mid}
    except Exception as e:
        log.warning("telegram photo exception type=%s", type(e).__name__)
        return {"sent": False, "error": str(e)[:200], "error_type": type(e).__name__}
