"""Whitelist-only Telegram inbound commands (no free-text trades).

Poll with:
  PYTHONPATH=. python -m src.notifications.bot_commands

Allowed chat: TELEGRAM_CHAT_ID only.
Commands: /start /help /status /health /pause /resume /scan
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from src.config import settings
from src.notifications.telegram import TELEGRAM_API, _post_telegram, send_telegram, telegram_configured

log = logging.getLogger("trading_core.telegram.commands")
API_BASE = "http://127.0.0.1:8080"
HELP_TEXT = (
    "<b>Trading Core bot</b> (paper only)\n"
    "/status — health + risk flags\n"
    "/scan — research scan (propose only)\n"
    "/pause — kill switch ON\n"
    "/resume — kill switch OFF\n"
    "/help — this message\n\n"
    "<i>No buy/sell commands. RiskEngine always applies.</i>"
)


def _allowed_chat(chat_id: Any) -> bool:
    expected = str(getattr(settings, "telegram_chat_id", "") or "")
    return bool(expected) and str(chat_id) == expected


def _api(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.request(method, url, **kwargs)
            if r.headers.get("content-type", "").startswith("application/json"):
                body: Any = r.json()
            else:
                body = r.text[:500]
            return {"ok": r.status_code < 400, "status_code": r.status_code, "body": body}
    except Exception as e:
        return {"ok": False, "error": str(e), "error_type": type(e).__name__}


def _answer_callback(token: str, callback_query_id: str, text: str = "") -> None:
    _post_telegram(
        "answerCallbackQuery",
        {"callback_query_id": callback_query_id, "text": text[:200]},
        token=token,
    )


def handle_command(text: str) -> str:
    cmd = (text or "").strip().split()[0].lower().split("@")[0]
    if cmd in ("/start", "/help"):
        return HELP_TEXT
    if cmd in ("/status", "/health"):
        h = _api("GET", "/health")
        if not h.get("ok"):
            return f"<b>API unreachable</b>\n<code>{h.get('error') or h}</code>"
        b = h["body"] if isinstance(h["body"], dict) else {}
        return (
            "<b>Trading Core · status</b>\n"
            f"status: <code>{b.get('status')}</code>\n"
            f"mode: <code>{b.get('trading_mode')}</code>\n"
            f"paused: <code>{b.get('trading_paused')}</code>\n"
            f"telegram: <code>{b.get('telegram_configured')}</code>\n"
            f"version: <code>{b.get('version')}</code>\n"
            "<i>Paper only</i>"
        )
    if cmd == "/pause":
        r = _api("POST", "/risk/pause")
        if r.get("ok"):
            return "<b>Trading PAUSED</b>\nKill switch active · paper only"
        return f"<b>Pause failed</b>\n<code>{r.get('error') or r}</code>"
    if cmd == "/resume":
        r = _api("POST", "/risk/resume")
        if r.get("ok"):
            return "<b>Trading resumed</b>\nKill switch cleared · paper only"
        return f"<b>Resume failed</b>\n<code>{r.get('error') or r}</code>"
    if cmd == "/scan":
        r = _api("POST", "/research/scan", params={"execute": "false", "max_notional": "100"})
        if not r.get("ok"):
            return f"<b>Scan failed</b>\n<code>{r.get('error') or r}</code>"
        body = r.get("body") if isinstance(r.get("body"), dict) else {}
        tg = body.get("telegram") or {}
        return (
            "<b>Scan done</b>\n"
            f"actions: <code>{len(body.get('actions') or [])}</code>\n"
            f"telegram: <code>{tg.get('sent')}</code>\n"
            "<i>Propose only · paper</i>"
        )
    return "Unknown command. Try /help"


def process_update(update: dict[str, Any], *, token: str) -> None:
    callback = update.get("callback_query")
    if callback:
        chat = (callback.get("message") or {}).get("chat") or {}
        if not _allowed_chat(chat.get("id")):
            _answer_callback(token, str(callback.get("id")), "Unauthorized")
            return
        data = callback.get("data") or ""
        _answer_callback(token, str(callback.get("id")), "OK" if data.startswith("noop") else "")
        return
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    if not _allowed_chat(chat.get("id")):
        return
    text = message.get("text") or ""
    if not text.startswith("/"):
        return
    send_telegram(handle_command(text))


def poll_forever(offset: int = 0) -> None:
    if not telegram_configured():
        raise SystemExit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required")
    token = settings.telegram_bot_token
    log.info("telegram command poller starting (whitelist chat only)")
    while True:
        try:
            url = f"{TELEGRAM_API}/bot{token}/getUpdates"
            with httpx.Client(timeout=35.0) as client:
                r = client.get(url, params={"offset": offset, "timeout": 25})
                data = r.json() if r.content else {}
            if not data.get("ok"):
                time.sleep(3)
                continue
            for upd in data.get("result") or []:
                offset = max(offset, int(upd.get("update_id", 0)) + 1)
                try:
                    process_update(upd, token=token)
                except Exception as e:
                    log.warning("process_update error: %s", e)
        except Exception as e:
            log.warning("poll loop error: %s", e)
            time.sleep(5)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    poll_forever()


if __name__ == "__main__":
    main()
