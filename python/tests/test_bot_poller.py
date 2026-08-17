"""Telegram long-poller (no live Telegram network)."""

from __future__ import annotations

from src.notifications import bot as botmod


def test_offset_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "offset.txt"
    monkeypatch.setattr(botmod, "OFFSET_PATH", path)
    assert botmod._read_offset() == 0
    botmod._write_offset(42)
    assert botmod._read_offset() == 42
    path.write_text("nope")
    assert botmod._read_offset() == 0


def test_process_updates_failed_get(monkeypatch, tmp_path):
    monkeypatch.setattr(botmod, "OFFSET_PATH", tmp_path / "o.txt")
    monkeypatch.setattr(botmod, "telegram_request", lambda *a, **k: {"ok": False, "error": "down"})
    assert botmod.process_updates() == 0


def test_process_updates_message_and_callbacks(monkeypatch, tmp_path):
    from src.notifications import telegram as tg

    monkeypatch.setattr(botmod, "OFFSET_PATH", tmp_path / "o.txt")
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(tg.settings, "telegram_bot_token", "tok")
    monkeypatch.setattr(
        botmod,
        "telegram_request",
        lambda *a, **k: {
            "ok": True,
            "result": [
                {"update_id": 10, "message": {"text": "/help", "chat": {"id": 7}}},
                {
                    "update_id": 11,
                    "callback_query": {
                        "id": "cb-ok",
                        "data": "noop:status",
                        "message": {"chat": {"id": 7}},
                    },
                },
                {
                    "update_id": 12,
                    "callback_query": {
                        "id": "cb-bad",
                        "data": "noop:status",
                        "message": {"chat": {"id": 99}},
                    },
                },
                {"update_id": 13, "message": {"text": "", "chat": {"id": 7}}},
            ],
        },
    )
    sent: list[str] = []
    answers: list[tuple[str, str]] = []
    monkeypatch.setattr(botmod, "handle_text", lambda text, chat_id: "HELP-BODY")
    monkeypatch.setattr(botmod, "send_telegram", lambda text: sent.append(text) or {"sent": True})
    monkeypatch.setattr(
        botmod, "_answer_callback", lambda cid, text="": answers.append((cid, text))
    )
    n = botmod.process_updates()
    assert n == 2
    assert sent == ["HELP-BODY"]
    assert ("cb-ok", "OK") in answers
    assert ("cb-bad", "Unauthorized") in answers
    assert botmod._read_offset() == 14


def test_answer_callback_no_token(monkeypatch):
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_bot_token", "")
    botmod._answer_callback("x", "hi")


def test_answer_callback_posts(monkeypatch):
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_bot_token", "tok")
    posted: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        botmod,
        "_post_telegram",
        lambda method, payload, token="": posted.append((method, payload)) or {"ok": True},
    )
    botmod._answer_callback("cb-1", "OK")
    assert posted[0][0] == "answerCallbackQuery"
    assert posted[0][1]["callback_query_id"] == "cb-1"


def test_process_updates_edited_message(monkeypatch, tmp_path):
    from src.notifications import telegram as tg

    monkeypatch.setattr(botmod, "OFFSET_PATH", tmp_path / "o.txt")
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(tg.settings, "telegram_bot_token", "tok")
    monkeypatch.setattr(
        botmod,
        "telegram_request",
        lambda *a, **k: {
            "ok": True,
            "result": [
                {
                    "update_id": 20,
                    "edited_message": {"text": "/help", "chat": {"id": 7}},
                },
                {
                    "update_id": 21,
                    "callback_query": {
                        "id": "cb-other",
                        "data": "trade:buy",
                        "message": {"chat": {"id": 7}},
                    },
                },
            ],
        },
    )
    answers: list[tuple[str, str]] = []
    monkeypatch.setattr(botmod, "handle_text", lambda text, chat_id: "HELP")
    monkeypatch.setattr(botmod, "send_telegram", lambda text: {"sent": True})
    monkeypatch.setattr(
        botmod, "_answer_callback", lambda cid, text="": answers.append((cid, text))
    )
    assert botmod.process_updates() == 2
    assert answers == [("cb-other", "")]


def test_main_exits_when_unconfigured(monkeypatch):
    monkeypatch.setattr(botmod, "telegram_configured", lambda: False)
    monkeypatch.setattr(botmod, "init_db", lambda: None)
    try:
        botmod.main()
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert exc.code == 1


def test_quote_price_mid_ask_bid_and_bars(monkeypatch):
    from src.copytrade import books as books_mod

    class _MD:
        def __init__(self):
            self.mode = "mid"

        def get_latest_quote(self, symbol):
            if self.mode == "mid":
                return {"bid": 10.0, "ask": 12.0}
            if self.mode == "ask":
                return {"bid": 0, "ask": 11.0}
            if self.mode == "bid":
                return {"bid": 9.0, "ask": 0}
            raise RuntimeError("no quote")

        def get_bars(self, symbol, limit=5):
            if self.mode == "bars":
                return [{"close": 8.5}]
            raise RuntimeError("no bars")

    md = _MD()
    monkeypatch.setattr("src.market_data.AlpacaMarketData", lambda: md)
    assert books_mod.quote_price("NVDA") == 11.0
    md.mode = "ask"
    assert books_mod.quote_price("NVDA") == 11.0
    md.mode = "bid"
    assert books_mod.quote_price("NVDA") == 9.0
    md.mode = "bars"
    assert books_mod.quote_price("NVDA") == 8.5
    md.mode = "none"
    assert books_mod.quote_price("NVDA") is None
