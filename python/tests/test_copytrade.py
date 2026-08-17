"""Public-disclosure copy-trade tests (no live network, no live capital)."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.feeds.congress import normalize_side, normalize_ticker
from src.feeds.sec13f import _pad_cik
from src.main import app

client = TestClient(app)


def test_feed_urls_prefer_public_mirrors():
    from src.feeds import congress

    assert any("githubusercontent.com" in u for u in congress.SENATE_URLS)
    assert any("githubusercontent.com" in u for u in congress.HOUSE_URLS)


def test_normalize_ticker_skips_junk():
    assert normalize_ticker("NVDA") == "NVDA"
    assert normalize_ticker("$aapl") == "AAPL"
    assert normalize_ticker("N/A") is None
    assert normalize_ticker("--") is None
    assert normalize_ticker("BRK.B") is None
    assert normalize_ticker("Call NVDA 100") is None


def test_normalize_side():
    assert normalize_side("Purchase") == "buy"
    assert normalize_side("Sale") == "sell"
    assert normalize_side("sale (partial)") == "sell"
    assert normalize_side("exchange") is None
    assert normalize_side("buy/sell") is None


def test_pad_cik():
    assert _pad_cik("1067983") == "0001067983"
    assert _pad_cik("0001067983") == "0001067983"


def test_format_copytrade_digest_escapes_html():
    from src.copytrade.engine import format_copytrade_digest

    html = format_copytrade_digest(
        {
            "mode": "propose_only",
            "lookback_days": 7,
            "max_notional": 100,
            "sentiment": {"ok": True, "value": 42, "label": "Fear <script>"},
            "new_disclosures": [
                {
                    "watchlist_match": "Nancy & Pelosi",
                    "side": "buy",
                    "symbol": "NVDA",
                    "amount": "$1,001 - $15,000",
                    "disclosure_date": "08/01/2026",
                }
            ],
            "actions": [
                {
                    "risk_decision": "ALLOW",
                    "executed": False,
                    "side": "buy",
                    "symbol": "NVDA",
                    "notional": 100,
                    "copied_from": "Nancy <Pelosi>",
                }
            ],
            "shadow_vs_paper": [],
            "investor_13f": [],
        }
    )
    assert "&amp;" in html
    assert "&lt;script&gt;" in html
    assert "Nancy &amp; Pelosi" in html
    assert "Nancy &lt;Pelosi&gt;" in html
    assert "<script>" not in html
    assert "Fear &amp; Greed" in html
    assert "propose_only" in html


def test_format_copytrade_digest_hides_http_errors():
    from src.copytrade.engine import format_copytrade_digest

    html = format_copytrade_digest(
        {
            "mode": "propose_only",
            "lookback_days": 45,
            "max_notional": 100,
            "sentiment": {
                "ok": False,
                "error": "Client error '403 Forbidden' for url 'https://api.alternative.me/fng'",
            },
            "feed_error": "Client error '403 Forbidden' for url 'https://example.invalid/x'",
            "new_disclosures": [],
            "actions": [],
            "shadow_vs_paper": [],
            "investor_13f": [
                {
                    "ok": False,
                    "name": "Warren Buffett",
                    "error": (
                        "Client error '403 Forbidden' for url "
                        "'https://data.sec.gov/submissions/CIK0001067983.json'"
                    ),
                }
            ],
        }
    )
    assert "data.sec.gov" not in html
    assert "https://" not in html
    assert "403 Forbidden" not in html
    assert "blocked (403)" in html
    assert "SEC blocked automated access (403)" in html
    assert "Warren Buffett" in html


def test_user_agent_is_sec_declared():
    from src.feeds.http import USER_AGENT

    assert "@" in USER_AGENT
    assert "noreply.github.com" not in USER_AGENT


def test_fetch_watchlist_trades_filters_and_maps(monkeypatch):
    from src.feeds import congress

    today = datetime.utcnow().strftime("%m/%d/%Y")
    old = (datetime.utcnow() - timedelta(days=40)).strftime("%m/%d/%Y")
    senate = [
        {
            "senator": "Nancy Pelosi",
            "ticker": "NVDA",
            "type": "Purchase",
            "amount": "$1,001 - $15,000",
            "disclosure_date": today,
            "transaction_date": today,
        },
        {
            "senator": "Nancy Pelosi",
            "ticker": "N/A",
            "type": "Purchase",
            "disclosure_date": today,
        },
        {
            "senator": "Someone Else",
            "ticker": "AAPL",
            "type": "Purchase",
            "disclosure_date": today,
        },
        {
            "senator": "Nancy Pelosi",
            "ticker": "MSFT",
            "type": "Purchase",
            "disclosure_date": old,
        },
    ]
    house = [
        {
            "representative": "Ro Khanna",
            "ticker": "GOOGL",
            "type": "Sale",
            "amount": "$15,001 - $50,000",
            "disclosure_date": today,
            "transaction_date": today,
        },
        {
            "representative": "Ro Khanna",
            "ticker": "GOOGM",
            "type": "Purchase",
            "asset_description": "Alphabet Inc. Series A Mandatory Convertible Preferred",
            "asset_type": "Stock",
            "disclosure_date": today,
            "transaction_date": today,
        },
    ]

    def fake_json(url: str, **_kwargs):
        if "senate" in url:
            return senate
        return house

    monkeypatch.setattr(congress, "get_json", fake_json)
    rows = congress.fetch_watchlist_trades(["Nancy Pelosi", "Ro Khanna"], lookback_days=7)
    symbols = {r["symbol"] for r in rows}
    assert symbols == {"NVDA", "GOOGL"}
    by_sym = {r["symbol"]: r for r in rows}
    assert by_sym["NVDA"]["side"] == "buy"
    assert by_sym["GOOGL"]["side"] == "sell"
    assert by_sym["NVDA"]["watchlist_match"] == "Nancy Pelosi"


def test_run_copytrade_daily_propose_only(monkeypatch, tmp_path):
    from src.copytrade import engine as eng
    from src.database import models  # noqa: F401
    from src.database.session import Base

    db_path = tmp_path / "copy.db"
    test_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(eng, "SessionLocal", TestSession)
    monkeypatch.setattr(eng, "init_db", lambda: None)
    monkeypatch.setattr(eng, "REPORTS_DIR", tmp_path)

    monkeypatch.setattr(
        eng,
        "fetch_fear_greed",
        lambda: {"ok": True, "value": 55, "label": "Greed"},
    )
    monkeypatch.setattr(
        eng,
        "fetch_watchlist_trades",
        lambda *_a, **_k: [
            {
                "event_key": "senate|Nancy Pelosi|NVDA|buy|08/01/2026||Purchase|$1,001",
                "source": "stock_act_senate",
                "filer": "Nancy Pelosi",
                "watchlist_match": "Nancy Pelosi",
                "symbol": "NVDA",
                "side": "buy",
                "amount": "$1,001 - $15,000",
                "disclosure_date": "08/01/2026",
            }
        ],
    )
    monkeypatch.setattr(
        eng,
        "fetch_manager_filings",
        lambda: [
            {"ok": True, "manager": "Warren Buffett", "form": "13F-HR", "filed": "2026-08-14"}
        ],
    )

    class FakePaper:
        def propose_and_validate(self, **kwargs):
            return {
                "symbol": kwargs["symbol"],
                "side": kwargs["side"],
                "notional": kwargs["notional"],
                "risk_decision": "ALLOW",
                "executed": False,
            }

        def execute_approved(self, **kwargs):
            raise AssertionError("propose-only run must not execute")

    monkeypatch.setattr(eng, "PaperExecutionEngine", lambda **_k: FakePaper())
    monkeypatch.setattr(
        eng,
        "research_watchlist_trades",
        lambda trades, **_k: {
            "window": {
                "count": len(trades),
                "buys": 1,
                "sells": 0,
                "top_buys": [{"symbol": "NVDA", "n": 1}],
            },
            "symbols": {},
        },
    )
    monkeypatch.setattr(
        eng,
        "_paper_overlap",
        lambda _shadows: [
            {
                "symbol": "NVDA",
                "paper_qty": "2",
                "paper_pl": "12.5",
                "owner": "Nancy Pelosi",
                "shadow_side": "buy",
            }
        ],
    )
    monkeypatch.setattr(
        eng,
        "send_telegram",
        lambda _text: {"sent": True, "message_id": 99},
    )

    report = eng.run_copytrade_daily(execute=False, notify=True, lookback_days=7, max_notional=100)
    assert report["mode"] == "propose_only"
    assert len(report["new_disclosures"]) == 1
    assert report["research"]["window"]["buys"] == 1
    assert report["actions"][0]["executed"] is False
    assert report["actions"][0]["copied_from"] == "Nancy Pelosi"
    assert report["telegram"]["sent"] is True
    assert (tmp_path / "copytrade_latest.json").exists()

    again = eng.run_copytrade_daily(execute=False, notify=False)
    assert again["new_disclosures"] == []


def test_run_copytrade_daily_execute_paper(monkeypatch, tmp_path):
    from src.copytrade import engine as eng
    from src.database import models  # noqa: F401
    from src.database.session import Base

    test_engine = create_engine(f"sqlite:///{tmp_path / 'copy.db'}")
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(eng, "SessionLocal", TestSession)
    monkeypatch.setattr(eng, "init_db", lambda: None)
    monkeypatch.setattr(eng, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(eng, "fetch_fear_greed", lambda: {"ok": False, "error": "skip"})
    monkeypatch.setattr(
        eng,
        "fetch_watchlist_trades",
        lambda *_a, **_k: [
            {
                "event_key": "house|Ro Khanna|GOOGL|sell|08/02/2026||Sale|$15,001",
                "source": "stock_act_house",
                "filer": "Ro Khanna",
                "watchlist_match": "Ro Khanna",
                "symbol": "GOOGL",
                "side": "sell",
                "amount": "$15,001 - $50,000",
                "disclosure_date": "08/02/2026",
            }
        ],
    )
    monkeypatch.setattr(eng, "fetch_manager_filings", lambda: [])

    class FakePaper:
        def propose_and_validate(self, **_kwargs):
            raise AssertionError("execute path should call execute_approved")

        def execute_approved(self, **kwargs):
            return {
                "symbol": kwargs["symbol"],
                "side": kwargs["side"],
                "notional": kwargs["notional"],
                "risk_decision": "ALLOW",
                "executed": True,
            }

    monkeypatch.setattr(eng, "PaperExecutionEngine", lambda **_k: FakePaper())
    monkeypatch.setattr(
        eng,
        "research_watchlist_trades",
        lambda trades, **_k: {
            "window": {"count": 1, "buys": 0, "sells": 1, "top_buys": []},
            "symbols": {},
        },
    )
    monkeypatch.setattr(eng, "_paper_overlap", lambda _s: [])
    report = eng.run_copytrade_daily(execute=True, notify=False, max_notional=100)
    assert report["mode"] == "execute_paper"
    assert report["actions"][0]["executed"] is True
    assert report["actions"][0]["notional"] == 100


def test_copytrade_watchlist_endpoint():
    response = client.get("/copytrade/watchlist")
    assert response.status_code == 200
    data = response.json()
    assert "Nancy Pelosi" in data["filers"]
    assert data["max_notional"] == 100
    assert data["lookback_days"] == 45
    assert data["execute_paper"] is False


def test_copytrade_latest_missing():
    response = client.get("/copytrade/latest")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data or "new_disclosures" in data


def test_copytrade_run_endpoint_mocked(monkeypatch):
    monkeypatch.setattr(
        "src.main.run_copytrade_daily",
        lambda **kwargs: {
            "mode": "propose_only",
            "execute": kwargs.get("execute"),
            "notify": kwargs.get("notify"),
            "new_disclosures": [],
        },
    )
    response = client.post("/copytrade/run", params={"notify": False, "execute": False})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "propose_only"
    assert data["notify"] is False


def test_health_includes_copytrade_flag():
    response = client.get("/health")
    assert response.status_code == 200
    assert "copytrade_execute_paper" in response.json()
