"""Telegram Bot alerts (paper trading notifications).

Env:
  TELEGRAM_BOT_TOKEN  — from @BotFather
  TELEGRAM_CHAT_ID    — your chat or group id

Outbound only by default. Optional inbound commands live in
`src.notifications.commands` / `src.notifications.bot` (whitelist chat id; no free-text trades).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

from src.config import settings

# Never let httpx INFO log the bot token (it is in the request URL path).
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TELEGRAM_API = "https://api.telegram.org"
log = logging.getLogger("trading_core.telegram")

# ~1 msg/s per chat is Telegram's practical limit; leave headroom.
_MIN_SEND_INTERVAL_SEC = 1.05
_send_lock = threading.Lock()
_last_send_monotonic = 0.0


def telegram_configured() -> bool:
    return bool(
        getattr(settings, "telegram_bot_token", "") and getattr(settings, "telegram_chat_id", "")
    )


def esc_html(text: Any) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def allowed_chat_id() -> str:
    return str(getattr(settings, "telegram_chat_id", "") or "")


def chat_allowed(chat_id: Any) -> bool:
    allowed = allowed_chat_id()
    return bool(allowed) and str(chat_id) == allowed


def telegram_request(
    method: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 35.0,
) -> dict[str, Any]:
    """Call a Telegram Bot API method. Never log the URL (token is in the path)."""
    token = getattr(settings, "telegram_bot_token", "") or ""
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not set"}
    url = f"{TELEGRAM_API}/bot{token}/{method}"
    try:
        with httpx.Client(timeout=timeout) as client:
            if json_body is not None:
                r = client.post(url, json=json_body)
            else:
                r = client.get(url, params=params or {})
            data = r.json() if r.content else {}
            if r.status_code != 200:
                return {
                    "ok": False,
                    "status_code": r.status_code,
                    "error": data.get("description") or r.text[:200],
                }
            return data if isinstance(data, dict) else {"ok": False, "error": "bad payload"}
    except Exception as exc:
        log.warning("telegram %s exception type=%s", method, type(exc).__name__)
        return {"ok": False, "error": str(exc)[:200], "error_type": type(exc).__name__}


def _throttle() -> None:
    """Serialize sends and space them to avoid flood control."""
    global _last_send_monotonic
    with _send_lock:
        now = time.monotonic()
        wait = _MIN_SEND_INTERVAL_SEC - (now - _last_send_monotonic)
        if wait > 0:
            time.sleep(wait)
        _last_send_monotonic = time.monotonic()


def _post_telegram(method: str, payload: dict[str, Any], *, token: str) -> dict[str, Any]:
    """POST to Telegram Bot API. Never log the full URL (token is in the path)."""
    url = f"{TELEGRAM_API}/bot{token}/{method}"
    last_error: str | None = None
    last_status: int | None = None

    for attempt in range(3):
        try:
            _throttle()
            with httpx.Client(timeout=20.0) as client:
                r = client.post(url, json=payload)
                data = r.json() if r.content else {}
                if r.status_code == 429 or (
                    isinstance(data, dict)
                    and "retry after" in str(data.get("description", "")).lower()
                ):
                    retry_after = 2.0
                    if isinstance(data, dict):
                        params = data.get("parameters") or {}
                        if "retry_after" in params:
                            retry_after = float(params["retry_after"]) + 0.25
                    log.warning(
                        "telegram rate limited method=%s retry_after=%.1fs", method, retry_after
                    )
                    time.sleep(retry_after)
                    continue
                if r.status_code != 200 or not data.get("ok"):
                    last_status = r.status_code
                    last_error = data.get("description") or r.text[:300]
                    # Transient 5xx — brief retry
                    if r.status_code >= 500 and attempt < 2:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    return {
                        "ok": False,
                        "status_code": r.status_code,
                        "error": last_error,
                        "data": data,
                    }
                return {"ok": True, "status_code": r.status_code, "data": data}
        except Exception as e:
            last_error = str(e)
            last_status = None
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            return {
                "ok": False,
                "error": last_error,
                "error_type": type(e).__name__,
            }

    return {
        "ok": False,
        "status_code": last_status,
        "error": last_error or "unknown",
    }


def send_telegram(
    text: str,
    *,
    parse_mode: str | None = "HTML",
    reply_markup: dict[str, Any] | None = None,
    disable_notification: bool = False,
) -> dict[str, Any]:
    """Send a message to the configured chat. No-op if not configured."""
    token = getattr(settings, "telegram_bot_token", "") or ""
    chat_id = getattr(settings, "telegram_chat_id", "") or ""
    if not token or not chat_id:
        log.debug("telegram send skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return {"sent": False, "reason": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"}

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text[:3900],
        "disable_web_page_preview": True,
        "disable_notification": disable_notification,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup

    result = _post_telegram("sendMessage", payload, token=token)
    if not result.get("ok"):
        error = result.get("error") or ""
        # HTML parse failures are common when a feed dumps raw URLs.
        if parse_mode and "parse" in str(error).lower():
            log.warning("telegram HTML parse failed, retrying plain text: %s", error)
            return send_telegram(
                text,
                parse_mode=None,
                reply_markup=reply_markup,
                disable_notification=disable_notification,
            )
        log.warning(
            "telegram send failed status=%s error=%s chars=%s",
            result.get("status_code"),
            error,
            len(text),
        )
        out: dict[str, Any] = {
            "sent": False,
            "status_code": result.get("status_code"),
            "error": error,
        }
        if result.get("error_type"):
            out["error_type"] = result["error_type"]
        return out

    data = result.get("data") or {}
    message_id = data.get("result", {}).get("message_id")
    log.info("telegram send ok message_id=%s chars=%s", message_id, len(text))
    return {"sent": True, "message_id": message_id}


def status_keyboard(dashboard_url: str | None = None) -> dict[str, Any]:
    """Inline keyboard for digests — URL only (no trade callbacks)."""
    rows: list[list[dict[str, str]]] = []
    if dashboard_url:
        rows.append([{"text": "📊 Dashboard", "url": dashboard_url}])
    rows.append(
        [
            {"text": "ℹ️ Status tip", "callback_data": "noop:status"},
        ]
    )
    return {"inline_keyboard": rows}


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


def format_heartbeat(
    *,
    trading_paused: bool,
    equity: Any = "—",
    weekday_timers: bool = True,
) -> str:
    """Compact weekend / idle status line."""
    lines = [
        "<b>Trading Core · heartbeat</b>",
        f"Equity: <code>{esc_html(equity)}</code>",
        f"Paused: <code>{trading_paused}</code>",
        f"Timers: <code>{'weekday only' if weekday_timers else 'custom'}</code>",
        "",
        "<i>Paper only · no scheduled research on weekends</i>",
    ]
    return "\n".join(lines)
