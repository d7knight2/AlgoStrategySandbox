"""Telegram notification helpers (no network required)."""

from unittest.mock import MagicMock

import pytest

from src.notifications.telegram import (
    format_heartbeat,
    format_scan_alert,
    send_telegram,
    status_keyboard,
    telegram_request,
)


@pytest.fixture(autouse=True)
def _fast_telegram(monkeypatch):
    monkeypatch.setattr("src.notifications.telegram._MIN_SEND_INTERVAL_SEC", 0)
    monkeypatch.setattr("src.notifications.telegram.time.sleep", lambda *_a, **_k: None)


def test_telegram_configured_false_without_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    # settings already cached — just ensure format works
    body = format_scan_alert(
        {
            "mode": "propose_only",
            "account_equity": 10000,
            "market_open": True,
            "signals": [{"symbol": "SPY"}],
            "actions": [
                {"symbol": "SPY", "side": "buy", "notional": 100, "risk_decision": "ALLOW"}
            ],
        }
    )
    assert "ALLOW" in body
    assert "SPY" in body
    assert "Paper only" in body or "paper" in body.lower()


def test_format_scan_no_actions():
    body = format_scan_alert(
        {
            "mode": "propose_only",
            "signals": [],
            "actions": [],
        }
    )
    assert "No actionable" in body


def test_send_telegram_exception_includes_type_not_token(monkeypatch):
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_bot_token", "SECRET-TOKEN-VALUE")
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "12345")

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.side_effect = RuntimeError("network down")
    monkeypatch.setattr(tg.httpx, "Client", lambda **_k: mock_client)

    result = send_telegram("hello")
    assert result["sent"] is False
    assert result["error_type"] == "RuntimeError"
    assert "SECRET-TOKEN-VALUE" not in str(result)


def test_send_telegram_http_error_logs_description(monkeypatch):
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_bot_token", "SECRET-TOKEN-VALUE")
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "12345")

    response = MagicMock()
    response.status_code = 400
    response.content = b'{"ok":false}'
    response.json.return_value = {"ok": False, "description": "chat not found"}
    response.text = "chat not found"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = response
    monkeypatch.setattr(tg.httpx, "Client", lambda **_k: mock_client)

    result = send_telegram("hello")
    assert result["sent"] is False
    assert result["status_code"] == 400
    assert "chat not found" in result["error"]
    assert "SECRET-TOKEN-VALUE" not in str(result)


def test_send_telegram_retries_plain_text_on_html_parse_error(monkeypatch):
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_bot_token", "SECRET-TOKEN-VALUE")
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "12345")

    bad = MagicMock()
    bad.status_code = 400
    bad.content = b'{"ok":false}'
    bad.json.return_value = {
        "ok": False,
        "description": "Bad Request: can't parse entities: Unsupported start tag",
    }
    bad.text = "can't parse entities"

    good = MagicMock()
    good.status_code = 200
    good.content = b'{"ok":true}'
    good.json.return_value = {"ok": True, "result": {"message_id": 42}}

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.side_effect = [bad, good]
    monkeypatch.setattr(tg.httpx, "Client", lambda **_k: mock_client)

    result = send_telegram("<b>hi</b> https://example.com/x")
    assert result["sent"] is True
    assert result["message_id"] == 42
    assert mock_client.post.call_count == 2
    assert mock_client.post.call_args_list[1].kwargs["json"].get("parse_mode") is None
    assert "SECRET-TOKEN-VALUE" not in str(result)


def test_send_telegram_retries_on_429(monkeypatch):
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_bot_token", "SECRET-TOKEN-VALUE")
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "12345")

    limited = MagicMock()
    limited.status_code = 429
    limited.content = b'{"ok":false}'
    limited.json.return_value = {
        "ok": False,
        "description": "Too Many Requests: retry after 1",
        "parameters": {"retry_after": 1},
    }
    limited.text = "retry after 1"

    good = MagicMock()
    good.status_code = 200
    good.content = b'{"ok":true}'
    good.json.return_value = {"ok": True, "result": {"message_id": 7}}

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.side_effect = [limited, good]
    monkeypatch.setattr(tg.httpx, "Client", lambda **_k: mock_client)

    result = send_telegram("hello")
    assert result["sent"] is True
    assert result["message_id"] == 7
    assert mock_client.post.call_count == 2
    assert "SECRET-TOKEN-VALUE" not in str(result)


def test_format_heartbeat_escapes_equity():
    body = format_heartbeat(trading_paused=False, equity="1000 <x>")
    assert "1000 &lt;x&gt;" in body
    assert "weekday only" in body
    custom = format_heartbeat(trading_paused=True, weekday_timers=False)
    assert "custom" in custom


def test_status_keyboard_url_only():
    kb = status_keyboard("https://example.invalid/dash")
    rows = kb["inline_keyboard"]
    assert rows[0][0]["url"] == "https://example.invalid/dash"
    assert rows[1][0]["callback_data"] == "noop:status"
    assert "buy" not in str(kb).lower()


def test_send_telegram_skipped_without_config(monkeypatch):
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_bot_token", "")
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "")
    out = send_telegram("hi")
    assert out["sent"] is False
    assert "not set" in out["reason"]


def test_telegram_request_no_token_and_http_error(monkeypatch):
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_bot_token", "")
    assert telegram_request("getUpdates")["ok"] is False

    monkeypatch.setattr(tg.settings, "telegram_bot_token", "SECRET-TOKEN-VALUE")
    response = MagicMock()
    response.status_code = 401
    response.content = b'{"ok":false}'
    response.json.return_value = {"ok": False, "description": "unauthorized"}
    response.text = "unauthorized"
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = response
    monkeypatch.setattr(tg.httpx, "Client", lambda **_k: mock_client)
    out = telegram_request("getUpdates", json_body={"timeout": 1})
    assert out["ok"] is False
    assert out["status_code"] == 401
    assert "SECRET-TOKEN-VALUE" not in str(out)


def test_telegram_request_ok_json(monkeypatch):
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_bot_token", "SECRET-TOKEN-VALUE")
    response = MagicMock()
    response.status_code = 200
    response.content = b'{"ok":true,"result":[]}'
    response.json.return_value = {"ok": True, "result": []}
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.get.return_value = response
    monkeypatch.setattr(tg.httpx, "Client", lambda **_k: mock_client)
    out = telegram_request("getMe", params={"a": 1})
    assert out["ok"] is True
    assert out["result"] == []


def test_format_scan_reject_only():
    body = format_scan_alert(
        {
            "mode": "propose_only",
            "signals": [{"symbol": "SPY"}],
            "actions": [{"symbol": "SPY", "side": "buy", "risk_decision": "REJECT"}],
        }
    )
    assert "No ALLOW" in body


def test_telegram_request_exception(monkeypatch):
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_bot_token", "SECRET-TOKEN-VALUE")

    class _Boom:
        def __enter__(self):
            raise RuntimeError("network down")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(tg.httpx, "Client", lambda **_k: _Boom())
    out = telegram_request("getMe")
    assert out["ok"] is False
    assert out["error_type"] == "RuntimeError"
    assert "SECRET-TOKEN-VALUE" not in str(out)


def test_status_keyboard_without_url():
    kb = status_keyboard(None)
    assert kb["inline_keyboard"][0][0]["callback_data"] == "noop:status"
    assert all("url" not in btn for row in kb["inline_keyboard"] for btn in row)
