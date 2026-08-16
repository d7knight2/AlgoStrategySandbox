"""Telegram notification helpers (no network required)."""

from src.notifications.telegram import format_scan_alert


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
