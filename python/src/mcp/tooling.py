"""MCP tool helpers: logging, error envelopes, Trading API client.

Failure JSON always includes tool, request_id, error_type, hint, and log_file
so an agent can diagnose without a traceback in the chat.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
import uuid
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

API_BASE = "http://127.0.0.1:8080"
LOG_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"
LOG_FILE = LOG_DIR / "mcp.log"
PARENT_LOGGER = "trading_core"
_FAILURES: deque[dict[str, Any]] = deque(maxlen=20)


def configure_logging() -> logging.Logger:
    """Attach stderr + file handlers to the trading_core logger once."""
    parent = logging.getLogger(PARENT_LOGGER)
    if parent.handlers:
        return logging.getLogger(f"{PARENT_LOGGER}.mcp")

    parent.setLevel(logging.DEBUG)
    parent.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    stream = logging.StreamHandler()
    stream.setLevel(logging.INFO)
    stream.setFormatter(fmt)
    parent.addHandler(stream)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        parent.addHandler(file_handler)
    except OSError as exc:
        parent.warning("mcp file log unavailable path=%s error=%s", LOG_FILE, exc)

    return logging.getLogger(f"{PARENT_LOGGER}.mcp")


def get_logger() -> logging.Logger:
    return configure_logging()


def clear_failures() -> None:
    _FAILURES.clear()


def recent_failures() -> list[dict[str, Any]]:
    return list(_FAILURES)


def hint_for(exc: BaseException) -> str:
    """Operator hint; never include secrets."""
    if isinstance(exc, httpx.ConnectError):
        return (
            "Trading API not reachable at 127.0.0.1:8080. "
            "Check: systemctl --user status trading-api.service"
        )
    if isinstance(exc, httpx.TimeoutException):
        return (
            "Trading API timed out. Check data/reports/api.log "
            "and whether a scan is blocking the server."
        )
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        path = exc.request.url.path
        return f"Trading API HTTP {status} for {exc.request.method} {path}"
    text = str(exc).lower()
    if "unauthorized" in text or "401" in text or "forbidden" in text:
        return "Auth failed. Confirm Alpaca keys in /etc/alpaca/env (do not print them)."
    return f"See {LOG_FILE} for traceback (request_id in this payload)."


def error_payload(
    tool: str,
    exc: BaseException,
    *,
    request_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "tool": tool,
        "request_id": request_id,
        "error_type": type(exc).__name__,
        "error": str(exc)[:800],
        "hint": hint_for(exc),
        "log_file": str(LOG_FILE),
    }
    if extra:
        payload.update(extra)
    if isinstance(exc, httpx.HTTPStatusError):
        payload["status_code"] = exc.response.status_code
        payload["response_body"] = (exc.response.text or "")[:400]
    return payload


def record_failure(payload: dict[str, Any], exc: BaseException | None = None) -> None:
    entry = {
        k: payload[k] for k in ("tool", "request_id", "error_type", "error", "hint") if k in payload
    }
    _FAILURES.append(entry)
    log = get_logger()
    log.error(
        "FAIL tool=%s request_id=%s error_type=%s error=%s",
        payload.get("tool"),
        payload.get("request_id"),
        payload.get("error_type"),
        payload.get("error"),
    )
    if exc is not None:
        log.debug("traceback request_id=%s\n%s", payload.get("request_id"), traceback.format_exc())


def safe_tool(tool: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    """Run a tool function and return JSON. Failures are logged + structured."""
    request_id = uuid.uuid4().hex[:10]
    log = get_logger()
    started = time.monotonic()
    log.info("START tool=%s request_id=%s", tool, request_id)
    try:
        result = fn(*args, **kwargs)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.info("OK tool=%s request_id=%s elapsed_ms=%s", tool, request_id, elapsed_ms)
        if isinstance(result, str):
            return result
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        payload = error_payload(tool, exc, request_id=request_id, extra={"elapsed_ms": elapsed_ms})
        record_failure(payload, exc)
        return json.dumps(payload, default=str, indent=2)


def api_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> Any:
    """Call the local Trading Core HTTP API. Logs status; never logs secrets."""
    log = get_logger()
    url = f"{API_BASE}{path}"
    log.info("API %s %s", method, path)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, url, params=params)
            if response.status_code >= 400:
                log.warning(
                    "API %s %s -> %s body=%s",
                    method,
                    path,
                    response.status_code,
                    (response.text or "")[:300],
                )
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as exc:
        log.warning("API %s %s failed: %s: %s", method, path, type(exc).__name__, exc)
        raise


def diagnostics() -> dict[str, Any]:
    """Read-only snapshot for debugging MCP + API + Telegram config."""
    from src.config import settings
    from src.notifications import telegram_configured

    log = get_logger()
    api: dict[str, Any]
    try:
        health = api_request("GET", "/health", timeout=8.0)
        api = {"reachable": True, "health": health}
    except Exception as exc:
        api = {
            "reachable": False,
            "error_type": type(exc).__name__,
            "error": str(exc)[:400],
            "hint": hint_for(exc),
        }
        log.warning("diagnostics: API health failed: %s: %s", type(exc).__name__, exc)

    return {
        "ok": bool(api.get("reachable")),
        "api_base": API_BASE,
        "api": api,
        "telegram_configured": telegram_configured(),
        "alpaca_keys_set": bool(settings.alpaca_api_key and settings.alpaca_secret_key),
        "trading_mode": settings.trading_mode,
        "log_file": str(LOG_FILE),
        "recent_failures": recent_failures(),
    }
