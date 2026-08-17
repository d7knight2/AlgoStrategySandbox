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
    assert nl_to_command("untrack Pelosi").startswith("/untrack")
    assert nl_to_command("hello") == "/help"
    assert nl_to_command("customize reports") == "/prefs"
    assert nl_to_command("account status") == "/status"
    assert nl_to_command("show my books") == "/books"
    assert nl_to_command("/already") == "/already"


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


def test_rate_limit_message(monkeypatch):
    import time as time_mod

    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 30)
    monkeypatch.setattr(cmds, "_LAST_CMD_AT", time_mod.monotonic())
    assert "Slow down" in handle_text("/help", chat_id="7")


def test_empty_text_returns_help(monkeypatch):
    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)
    assert "Paper only" in handle_text("   ", chat_id="7")


def test_gov_sells_and_feed_error(monkeypatch, tmp_path):
    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    _session(tmp_path, monkeypatch)
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)
    monkeypatch.setattr(
        cmds,
        "fetch_watchlist_trades",
        lambda watch, lookback_days=45: [
            {
                "watchlist_match": "Pelosi",
                "side": "sell",
                "symbol": "NVDA",
                "amount": "$1,001 - $15,000",
                "disclosure_date": "08/01/2026",
            },
            {
                "watchlist_match": "Pelosi",
                "side": "buy",
                "symbol": "AAPL",
                "amount": "$1,001 - $15,000",
                "disclosure_date": "08/02/2026",
            },
        ],
    )
    sells = handle_text("/gov sells Pelosi 30", chat_id="7")
    assert "Public sells" in sells
    assert "NVDA" in sells
    assert "AAPL" not in sells
    buys = handle_text("/gov buys Pelosi", chat_id="7")
    assert "AAPL" in buys
    monkeypatch.setattr(
        cmds,
        "fetch_watchlist_trades",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")),
    )
    assert "unavailable" in handle_text("/gov sells Pelosi", chat_id="7")


def test_prefs_weekly_off_and_helpers(monkeypatch, tmp_path):
    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    _session(tmp_path, monkeypatch)
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)
    out = handle_text("/prefs weekly off daily off progress off", chat_id="7")
    assert "False" in out
    assert cmds.should_send_weekly() is False
    assert cmds.should_send_daily_copytrade() is False
    assert cmds.should_send_progress() is False
    handle_text("/prefs digest full weekly on daily on progress on", chat_id="7")
    assert cmds.digest_style() == "full"
    assert cmds.should_send_weekly() is True


def test_track_usage_untrack_and_books(monkeypatch, tmp_path):
    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    _session(tmp_path, monkeypatch)
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)
    monkeypatch.setattr(cmds, "fetch_watchlist_trades", lambda *a, **k: [])
    monkeypatch.setattr(cmds, "quote_price", lambda s: None)
    assert "Usage" in handle_text("/track", chat_id="7")
    assert "Need a politician" in handle_text("/track Ab", chat_id="7")
    handle_text("/track Pelosi", chat_id="7")
    books = handle_text("/books", chat_id="7")
    assert "Pelosi" in books
    detail = handle_text("/book Pelosi", chat_id="7")
    assert "paper book" in detail
    assert "No book matching" in handle_text("/book Nobody", chat_id="7")
    assert "Usage" in handle_text("/untrack", chat_id="7")
    stopped = handle_text("/untrack Pelosi", chat_id="7")
    assert "Stopped auto-copy" in stopped
    assert "No paper book" in handle_text(
        "/untrack Zzz", chat_id="7"
    ) or "not found" in handle_text("/untrack MissingName", chat_id="7")


def test_scan_and_pause(monkeypatch):
    from unittest.mock import MagicMock

    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)

    class _Resp:
        status_code = 200
        content = b'{"actions":[1],"telegram":{"sent":true}}'

        def json(self):
            return {"actions": [1], "telegram": {"sent": True}}

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = _Resp()
    monkeypatch.setattr("httpx.Client", lambda **_k: mock_client)
    out = handle_text("/scan", chat_id="7")
    assert "Scan done" in out
    assert "propose only" in out.lower() or "Propose only" in out

    class _Engine:
        def pause_trading(self):
            self.paused = True

        def resume_trading(self):
            self.paused = False

    eng = _Engine()
    monkeypatch.setattr("src.main.risk_engine", eng)
    assert "paused" in handle_text("/pause", chat_id="7").lower()
    assert "resumed" in handle_text("/resume", chat_id="7").lower()


def test_report_copy_missing_and_weekly(monkeypatch, tmp_path):
    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    _session(tmp_path, monkeypatch)
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)
    monkeypatch.setattr(cmds, "REPORTS_DIR", tmp_path)
    missing = handle_text("/report copy", chat_id="7")
    assert "No copy-trade digest" in missing
    (tmp_path / "copytrade_latest.json").write_text(
        '{"mode":"propose_only","lookback_days":7,"max_notional":100,'
        '"sentiment":{},"new_disclosures":[],"actions":[]}'
    )
    digest = handle_text("/report copy", chat_id="7")
    assert "daily copy-trade digest" in digest
    monkeypatch.setattr(
        "src.reporting.weekly.generate_weekly_report",
        lambda notify=False: {
            "account": {"equity": 1.0},
            "positions": [],
            "week_return_pct": None,
            "unrealized_pl": 0,
            "ptr_week": {},
            "books": [],
        },
    )
    weekly = handle_text("/report weekly", chat_id="7")
    assert "weekly paper funds" in weekly
    assert "/track Pelosi" in weekly


def test_status_and_positions_mocked(monkeypatch, tmp_path):
    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    _session(tmp_path, monkeypatch)
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)
    create_book("Nancy Pelosi", starting_cash=10000)

    class _Broker:
        def get_account(self):
            return {"equity": 1234.5, "cash": 100.0}

        def get_market_status(self):
            return {"is_open": False}

        def get_positions(self):
            return [{"symbol": "NVDA", "qty": "1", "unrealized_pl": 2.5}]

    class _Limits:
        trading_paused = False

    class _Engine:
        limits = _Limits()

    monkeypatch.setattr("src.broker.AlpacaBroker", _Broker)
    monkeypatch.setattr("src.main.risk_engine", _Engine())
    monkeypatch.setattr(cmds, "quote_price", lambda s: 100.0)
    status = handle_text("/status", chat_id="7")
    assert "1,234.50" in status or "1234.50" in status
    health = handle_text("/health", chat_id="7")
    assert "Paper account" in health
    pos = handle_text("/positions", chat_id="7")
    assert "NVDA" in pos
    assert "Nancy Pelosi" in pos


def test_telegram_command_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    from src.main import app
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    client = TestClient(app)
    response = client.post("/telegram/command", params={"text": "/help", "chat_id": "7"})
    assert response.status_code == 200
    assert "Paper only" in response.json()["reply"]
    ignored = client.post("/telegram/command", params={"text": "/help", "chat_id": "999"})
    assert ignored.json()["ignored"] is True


def test_create_book_http(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from src.main import app

    _session(tmp_path, monkeypatch)
    client = TestClient(app)
    response = client.post(
        "/copytrade/books", params={"filer": "Tuberville", "starting_cash": 5000}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["filer"] == "Tuberville"


def test_weekly_report_pref_off(monkeypatch, tmp_path):
    from src.database.models import TelegramPref
    from src.reporting.weekly import generate_weekly_report

    Session = _session(tmp_path, monkeypatch)
    monkeypatch.setattr("src.reporting.weekly.SessionLocal", Session)
    monkeypatch.setattr("src.reporting.weekly.REPORTS_DIR", tmp_path)
    db = Session()
    try:
        db.add(TelegramPref(id=1, weekly_enabled=False))
        db.commit()
    finally:
        db.close()

    class _Broker:
        def get_account(self):
            return {"equity": 100.0}

        def get_positions(self):
            return []

    monkeypatch.setattr("src.reporting.weekly.AlpacaBroker", _Broker)
    monkeypatch.setattr("src.reporting.weekly.list_book_snapshots", lambda fetch_prices=True: [])
    report = generate_weekly_report(notify=True)
    assert report["telegram"]["sent"] is False
    assert report["telegram"]["reason"] == "weekly pref off"
    assert (tmp_path / "weekly_latest.json").exists()


def test_filer_book_edges(monkeypatch, tmp_path):
    from src.copytrade.books import any_book_wants_execute, book_snapshot, tracked_filer_names

    _session(tmp_path, monkeypatch)
    assert create_book("X")["ok"] is False
    created = create_book("Pelosi", starting_cash=50)
    assert created["starting_cash"] == 100.0
    again = create_book("Pelosi", starting_cash=5000)
    assert again["created"] is False
    trade = {
        "event_key": "k1",
        "watchlist_match": "Pelosi",
        "filer": "Pelosi",
        "symbol": "NVDA",
        "side": "buy",
    }
    assert apply_virtual_fill(trade, price=0)[0]["ok"] is False
    first = apply_virtual_fill(trade, price=10.0, notional_cap=100.0)
    assert first[0]["ok"] is True
    dup = apply_virtual_fill(trade, price=10.0, notional_cap=100.0)
    assert dup[0].get("skipped") == "already in book"
    sell_empty = apply_virtual_fill(
        {
            "event_key": "k-sell-aapl",
            "watchlist_match": "Pelosi",
            "symbol": "AAPL",
            "side": "sell",
        },
        price=10.0,
    )
    assert sell_empty[0]["ok"] is False
    assert any_book_wants_execute("Nancy Pelosi") is True
    assert "Pelosi" in tracked_filer_names()
    snap = book_snapshot("Pelosi", fetch_prices=False)
    assert snap is not None
    assert snap["filer"] == "Pelosi"


def test_seed_backfill_marks_seen(monkeypatch, tmp_path):
    from src.copytrade.engine import _already_seen
    from src.notifications import commands as cmds

    Session = _session(tmp_path, monkeypatch)
    create_book("Pelosi", starting_cash=1000)
    monkeypatch.setattr(
        cmds,
        "fetch_watchlist_trades",
        lambda *a, **k: [
            {
                "event_key": "house|Pelosi|NVDA|buy|1",
                "watchlist_match": "Pelosi",
                "filer": "Pelosi",
                "symbol": "NVDA",
                "side": "buy",
            }
        ],
    )
    monkeypatch.setattr(cmds, "quote_price", lambda s: 50.0)
    out = cmds._seed_and_backfill("Pelosi")
    assert out["fills"] == 1
    assert out["seen"] == 1
    db = Session()
    try:
        assert _already_seen(db, "house|Pelosi|NVDA|buy|1") is True
    finally:
        db.close()
    monkeypatch.setattr(
        cmds, "fetch_watchlist_trades", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    assert cmds._seed_and_backfill("Pelosi") == {"fills": 0, "seen": 0}


def test_books_empty_cash_and_unsupported_side(monkeypatch, tmp_path):
    from src.copytrade.books import apply_virtual_fill, books_matching, create_book

    _session(tmp_path, monkeypatch)
    assert apply_virtual_fill({"watchlist_match": "Nobody"}, price=10.0) == []
    assert books_matching("Nobody") == []
    create_book("Pelosi", starting_cash=100)
    trade = {
        "event_key": "k-buy",
        "watchlist_match": "Pelosi",
        "symbol": "NVDA",
        "side": "buy",
    }
    first = apply_virtual_fill(trade, price=10.0, notional_cap=100.0)
    assert first[0]["ok"] is True
    empty = apply_virtual_fill(
        {**trade, "event_key": "k-buy-2", "symbol": "AAPL"},
        price=10.0,
        notional_cap=100.0,
    )
    assert empty[0]["ok"] is False
    assert "cash empty" in empty[0]["error"]
    bad_side = apply_virtual_fill(
        {**trade, "event_key": "k-hold", "side": "hold"},
        price=10.0,
    )
    assert bad_side[0]["ok"] is False


def test_scan_http_error_and_command_exception(monkeypatch):
    from unittest.mock import MagicMock

    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)

    class _Resp:
        status_code = 500
        text = "boom"
        content = b"boom"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = _Resp()
    monkeypatch.setattr("httpx.Client", lambda **_k: mock_client)
    assert "Scan failed" in handle_text("/scan", chat_id="7")

    monkeypatch.setattr("httpx.Client", lambda **_k: (_ for _ in ()).throw(RuntimeError("down")))
    assert "Scan failed" in handle_text("/scan", chat_id="7")

    monkeypatch.setattr(cmds, "_dispatch", lambda *a, **k: (_ for _ in ()).throw(ValueError("x")))
    assert "Could not run" in handle_text("/help", chat_id="7")


def test_gov_empty_window_and_book_usage(monkeypatch, tmp_path):
    from src.notifications import commands as cmds
    from src.notifications import telegram as tg

    _session(tmp_path, monkeypatch)
    monkeypatch.setattr(tg.settings, "telegram_chat_id", "7")
    monkeypatch.setattr(cmds, "_RATE_S", 0)
    monkeypatch.setattr(cmds, "fetch_watchlist_trades", lambda *a, **k: [])
    monkeypatch.setattr(cmds, "quote_price", lambda s: None)
    empty = handle_text("/gov sells", chat_id="7")
    assert "None in this window" in empty
    assert "No politician paper books" in handle_text("/books", chat_id="7")
    handle_text("/track Pelosi", chat_id="7")
    assert "Politician paper books" in handle_text("/book", chat_id="7")


def test_weekly_report_broker_error_and_notify(monkeypatch, tmp_path):
    from src.reporting.weekly import generate_weekly_report

    Session = _session(tmp_path, monkeypatch)
    monkeypatch.setattr("src.reporting.weekly.SessionLocal", Session)
    monkeypatch.setattr("src.reporting.weekly.REPORTS_DIR", tmp_path)

    class _Broker:
        def get_account(self):
            raise RuntimeError("alpaca down")

        def get_positions(self):
            raise RuntimeError("alpaca down")

    monkeypatch.setattr("src.reporting.weekly.AlpacaBroker", _Broker)
    monkeypatch.setattr(
        "src.reporting.weekly.list_book_snapshots",
        lambda fetch_prices=True: [
            {
                "filer": "Pelosi",
                "enabled": True,
                "equity": 100.0,
                "return_pct": 0.0,
                "positions": [],
            }
        ],
    )
    sent: list[str] = []
    monkeypatch.setattr(
        "src.reporting.weekly.send_telegram", lambda text: sent.append(text) or {"sent": True}
    )
    report = generate_weekly_report(notify=True)
    assert "error" in report["account"]
    assert report["telegram"]["sent"] is True
    assert sent and "Pelosi" in sent[0]


def test_weekly_http_endpoint(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from src.main import app

    _session(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "src.reporting.weekly.generate_weekly_report",
        lambda notify=True: {"ok": True, "telegram": {"sent": False}, "account": {}},
    )
    client = TestClient(app)
    response = client.post("/reports/weekly")
    assert response.status_code == 200
    assert response.json()["ok"] is True
