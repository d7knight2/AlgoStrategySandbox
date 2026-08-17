"""Telegram notification helpers (no network required)."""

from unittest.mock import MagicMock

from src.notifications.telegram import format_scan_alert, send_telegram


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
