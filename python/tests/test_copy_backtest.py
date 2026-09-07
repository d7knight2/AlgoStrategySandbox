"""Offline copy-backtest of public STOCK Act rows (no Alpaca, no AI)."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def _bar(day: datetime, close: float) -> dict:
    return {
        "timestamp": day.isoformat(),
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 1000,
    }


def test_backtest_copy_filer_offline(monkeypatch):
    from src.copytrade import copy_backtest as cb

    start = datetime(2026, 1, 5)
    trades = [
        {
            "symbol": "NVDA",
            "side": "buy",
            "watchlist_match": "Nancy Pelosi",
            "transaction_date": "01/05/2026",
            "disclosure_date": "01/15/2026",
        },
        {
            "symbol": "NVDA",
            "side": "sell",
            "watchlist_match": "Nancy Pelosi",
            "transaction_date": "02/01/2026",
            "disclosure_date": "02/10/2026",
        },
    ]
    bars = [_bar(start + timedelta(days=i), 100 + i) for i in range(50)]
    monkeypatch.setattr(cb, "fetch_watchlist_trades", lambda *_a, **_k: trades)
    monkeypatch.setattr(cb, "_bars_index", lambda *_a, **_k: bars)

    out = cb.backtest_copy_filer("Nancy Pelosi", lookback_days=90, starting_cash=10_000)
    assert out["filer"] == "Nancy Pelosi"
    assert out["fills_executed"] == 2
    assert out["use_disclosure_date"] is True
    assert out["median_lag_days"] == 10
    buy = next(f for f in out["fills"] if f["side"] == "buy" and not f.get("skipped"))
    assert buy["lag_days"] == 10
    assert out["final_equity"] > 0
    assert "not financial advice" in " ".join(out["notes"]).lower()


def test_backtest_leaderboard_route_not_captured_as_filer(monkeypatch):
    monkeypatch.setattr(
        "src.copytrade.copy_backtest.backtest_leaderboard",
        lambda filers, **_k: {
            "leaderboard": [{"filer": f, "total_return_pct": 1.0} for f in filers],
            "ok": True,
        },
    )
    monkeypatch.setattr(
        "src.copytrade.copy_backtest.backtest_copy_filer",
        lambda filer, **_k: {"filer": filer, "wrong": True},
    )
    response = client.get("/copytrade/backtest/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert "leaderboard" in data
    assert data.get("wrong") is not True
