"""Telegram inbound commands + politician paper books (no live network)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.copytrade.books import apply_virtual_fill, create_book, disable_book, mark_book
from src.copytrade.engine import format_copytrade_digest
from src.database.models import FilerBook, FilerBookLot
from src.database.session import Base
from src.notifications.commands import handle_text, nl_to_command
from src.notifications.telegram import chat_allowed, esc_html
from src.reporting.weekly import format_weekly_digest


@pytest.fixture(autouse=True)
def _fast_commands(monkeypatch):
    monkeypatch.setattr("src.notifications.commands._RATE_S", 0)
    monkeypatch.setattr("src.notifications.commands._LAST_CMD_AT", 0.0)


def _session(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'tg.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr("src.copytrade.books.SessionLocal", Session)
    monkeypatch.setattr("src.notifications.commands.SessionLocal", Session)
    monkeypatch.setattr("src.copytrade.engine.SessionLocal", Session)
    return Session


def test_chat_allowlist(monkeypatch):
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_chat_id", "99")
    assert chat_allowed("99") is True
    assert chat_allowed("100") is False
    assert chat_allowed("") is False


def test_unknown_chat_is_silent(monkeypatch):
    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_chat_id", "99")
    monkeypatch.setattr(cmds, "_RATE_S", 0)
    assert handle_text("/help", chat_id="1") == ""
    assert "Paper only" in handle_text("/help", chat_id="99")


def test_nl_maps_portfolio_and_sells():
    assert nl_to_command("how is my paper portfolio") == "/positions"
    assert nl_to_command("how good are the paper funds") == "/weekly"
    assert "/gov sells" in nl_to_command("government sells Pelosi")
    assert nl_to_command("track Nancy Pelosi").startswith("/track")


def test_no_buy_sell_commands(monkeypatch):
    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)
    body = handle_text("/buy NVDA", chat_id="7")
    assert "Unknown command" in body
    help_txt = handle_text("/help", chat_id="7")
    assert "No /buy or /sell" in help_txt
    assert "/scan" in help_txt


def test_prefs_and_short_digest(monkeypatch, tmp_path):
    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    _session(tmp_path, monkeypatch)
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)
    out = handle_text("/prefs digest short", chat_id="7")
    assert "short" in out
    html = format_copytrade_digest(
        {
            "mode": "propose_only",
            "lookback_days": 45,
            "max_notional": 100,
            "sentiment": {"ok": True, "value": 40, "label": "Fear"},
            "new_disclosures": [],
            "actions": [],
            "shadow_vs_paper": [
                {"symbol": "NVDA", "paper_qty": "1", "owner": "X", "shadow_side": "buy"}
            ],
            "investor_13f": [
                {"ok": True, "name": "Buffett", "form": "13F-HR", "filed": "2026-08-14"}
            ],
        },
        style="short",
    )
    assert "Famous-investor" not in html
    assert "Paper vs tracked" not in html


def test_filer_book_virtual_buy_sell_and_mark(monkeypatch, tmp_path):
    Session = _session(tmp_path, monkeypatch)
    created = create_book("Nancy Pelosi", starting_cash=1000, auto_execute=True)
    assert created["ok"] is True
    trade = {
        "event_key": "house|Nancy Pelosi|NVDA|buy|1",
        "watchlist_match": "Nancy Pelosi",
        "filer": "Nancy Pelosi",
        "symbol": "NVDA",
        "side": "buy",
    }
    applied = apply_virtual_fill(trade, price=100.0, notional_cap=100.0)
    assert applied[0]["ok"] is True
    sell = dict(trade, event_key="house|Nancy Pelosi|NVDA|sell|2", side="sell")
    sold = apply_virtual_fill(sell, price=110.0, notional_cap=100.0)
    assert sold[0]["ok"] is True
    db = Session()
    try:
        book = db.query(FilerBook).first()
        lots = db.query(FilerBookLot).all()
        snap = mark_book(book, lots, {"NVDA": 110.0})
    finally:
        db.close()
    assert snap["cash"] == 1010.0
    assert disable_book("Pelosi")["ok"] is True


def test_weekly_digest_html():
    html = format_weekly_digest(
        {
            "account": {"equity": 10050.0},
            "positions": [{"symbol": "NVDA", "unrealized_pl": 12.0}],
            "week_return_pct": 0.5,
            "unrealized_pl": 12.0,
            "ptr_week": {"buys": 2, "sells": 1, "copied": 1},
            "books": [
                {
                    "filer": "Nancy Pelosi",
                    "enabled": True,
                    "equity": 10100.0,
                    "return_pct": 1.0,
                    "positions": [{"symbol": "NVDA"}],
                }
            ],
        }
    )
    assert "weekly paper funds" in html
    assert "Nancy Pelosi" in html
    assert "+1.0%" in html
    assert "<script" not in html.lower()


def test_track_creates_book_without_dumping_alpaca(monkeypatch, tmp_path):
    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    Session = _session(tmp_path, monkeypatch)
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)
    monkeypatch.setattr(cmds, "fetch_watchlist_trades", lambda *a, **k: [])
    out = handle_text("/track Pelosi 2500", chat_id="7")
    assert "Paper book" in out
    assert "Pelosi" in out
    assert "2500" in out or "2,500" in out
    db = Session()
    try:
        book = db.query(FilerBook).one()
        assert book.filer_key == "Pelosi"
        assert book.enabled is True
        assert book.auto_execute is True
        assert book.starting_cash == 2500.0
    finally:
        db.close()


def test_copytrade_books_endpoint(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from src.main import app

    _session(tmp_path, monkeypatch)
    create_book("Nancy Pelosi", starting_cash=10000, auto_execute=True)
    client = TestClient(app)
    response = client.get("/copytrade/books")
    assert response.status_code == 200
    names = [b["filer"] for b in response.json()["books"]]
    assert "Nancy Pelosi" in names


def test_bot_commands_compat_entrypoint(monkeypatch):
    from src.notifications import telegram as tg
    from src.notifications.bot_commands import handle_command

    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr("src.notifications.commands._RATE_S", 0)
    assert "Paper only" in handle_command("/help")


def test_esc_html():
    assert esc_html("A & B <c>") == "A &amp; B &lt;c&gt;"
