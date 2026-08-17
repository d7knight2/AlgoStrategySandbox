"""Government-trade research: Reddit, 7d/30d stats, leveraged products."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.copytrade.engine import format_copytrade_digest
from src.copytrade.research import pick_symbols, research_watchlist_trades, window_summary
from src.copytrade.stats import price_stats, trailing_return_pct
from src.feeds.http import friendly_feed_error
from src.feeds.leverage import classify_instrument
from src.feeds.reddit import score_posts


def _bar(day: datetime, close: float, volume: int = 1000) -> dict:
    return {
        "timestamp": day.isoformat(),
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": volume,
    }


def test_classify_leveraged_catalog():
    tqqq = classify_instrument("TQQQ")
    assert tqqq["leveraged"] is True
    assert tqqq["factor"] == 3
    assert tqqq["direction"] == "long"
    assert "Nasdaq" in tqqq["label"]

    sqqq = classify_instrument("SQQQ")
    assert sqqq["direction"] == "short"

    nvda = classify_instrument("NVDA", "NVIDIA Corporation Common Stock")
    assert nvda["leveraged"] is False
    assert nvda["kind"] == "common_stock"


def test_classify_from_asset_name():
    row = classify_instrument("XYZ", "Direxion Daily Semiconductors Bull 3X Shares")
    assert row["leveraged"] is True
    assert row["factor"] == 3
    covered = classify_instrument("NVDY", "YieldMax NVDA Option Income Strategy ETF")
    assert covered["leveraged"] is False
    assert covered["kind"] == "covered_call_etf"


def test_trailing_and_post_buy_stats():
    start = datetime(2026, 6, 1)
    bars = [_bar(start + timedelta(days=i), 100 + i, volume=1000 + i * 10) for i in range(40)]
    last = bars[-1]["close"]
    ret7 = trailing_return_pct(bars, 7)
    assert ret7 is not None
    assert 4.0 < ret7 < 8.0

    buy_day = start + timedelta(days=5)  # close 105
    stats = price_stats(bars, event_date=buy_day, side="buy")
    assert stats["ok"] is True
    assert stats["last"] == last
    assert stats["fwd_7d_ready"] is True
    assert stats["fwd_30d_ready"] is True
    assert stats["fwd_7d_pct"] == round((112 / 105 - 1) * 100, 2)
    assert stats["fwd_30d_pct"] == round((135 / 105 - 1) * 100, 2)
    assert stats["since_event_pct"] == round((last / 105 - 1) * 100, 2)


def test_reddit_score_posts_bullish_and_gov():
    posts = [
        {"title": "NVDA buy the dip bullish moon", "selftext": "", "score": 40},
        {"title": "Pelosi bought more NVDA calls", "selftext": "congress disclosure", "score": 20},
        {"title": "this is a crash dump sell", "selftext": "", "score": 5},
    ]
    out = score_posts(posts)
    assert out["mentions"] == 3
    assert out["bullish"] >= 1
    assert out["gov_mentions"] >= 1
    assert out["label"] in {"bullish", "mixed"}
    assert "NVDA" in out["sample"][0]


def test_window_summary_and_pick_symbols():
    trades = [
        {"symbol": "NVDA", "side": "buy", "watchlist_match": "Nancy Pelosi"},
        {"symbol": "NVDA", "side": "buy", "watchlist_match": "Nancy Pelosi"},
        {"symbol": "TQQQ", "side": "buy", "watchlist_match": "Tommy Tuberville"},
        {"symbol": "GOOGL", "side": "sell", "watchlist_match": "Ro Khanna"},
    ]
    summary = window_summary(trades)
    assert summary["buys"] == 3
    assert summary["sells"] == 1
    assert summary["top_buys"][0] == {"symbol": "NVDA", "n": 2}
    assert pick_symbols(trades, limit=2) == ["NVDA", "TQQQ"]


def test_research_bundle_offline(monkeypatch):
    monkeypatch.setattr(
        "src.copytrade.research.fetch_reddit_sentiment",
        lambda symbol, **_k: {
            "ok": True,
            "symbol": symbol,
            "mentions": 4,
            "label": "bullish",
            "net": 3,
            "gov_mentions": 1,
        },
    )
    start = datetime(2026, 6, 1)
    bars = [_bar(start + timedelta(days=i), 50 + i) for i in range(35)]
    monkeypatch.setattr("src.copytrade.research._load_bars", lambda _sym: (bars, None))
    trades = [
        {
            "symbol": "TQQQ",
            "side": "buy",
            "watchlist_match": "Nancy Pelosi",
            "asset": "ProShares UltraPro QQQ",
            "transaction_date": "06/01/2026",
            "disclosure_date": "07/15/2026",
            "amount": "$1,001 - $15,000",
        }
    ]
    bundle = research_watchlist_trades(trades)
    row = bundle["symbols"]["TQQQ"]
    assert row["instrument"]["leveraged"] is True
    assert row["stats"]["ok"] is True
    assert row["stats"]["fwd_7d_ready"] is True
    assert row["reddit"]["label"] == "bullish"
    assert bundle["window"]["buys"] == 1


def test_digest_includes_research_and_leverage():
    html = format_copytrade_digest(
        {
            "mode": "propose_only",
            "lookback_days": 45,
            "max_notional": 100,
            "sentiment": {"ok": True, "value": 40, "label": "Fear"},
            "new_disclosures": [
                {
                    "watchlist_match": "Nancy Pelosi",
                    "side": "buy",
                    "symbol": "TQQQ",
                    "amount": "$1,001 - $15,000",
                    "disclosure_date": "08/01/2026",
                }
            ],
            "actions": [],
            "shadow_vs_paper": [],
            "investor_13f": [],
            "research": {
                "window": {
                    "buys": 1,
                    "sells": 0,
                    "top_buys": [{"symbol": "TQQQ", "n": 1}],
                },
                "symbols": {
                    "TQQQ": {
                        "instrument": {
                            "leveraged": True,
                            "label": "3x long Nasdaq-100",
                        },
                        "stats": {
                            "ok": True,
                            "ret_7d_pct": 2.5,
                            "ret_30d_pct": -4.0,
                            "vol_7d_vs_30d": 1.3,
                            "event_date": "2026-07-01",
                            "since_event_pct": 8.0,
                            "fwd_7d_ready": True,
                            "fwd_7d_pct": 1.2,
                            "fwd_30d_ready": True,
                            "fwd_30d_pct": 6.5,
                        },
                        "reddit": {
                            "ok": True,
                            "mentions": 12,
                            "label": "bullish",
                            "net": 5,
                            "gov_mentions": 2,
                        },
                    }
                },
            },
        }
    )
    assert "Watchlist window" in html
    assert "Ticker research" in html
    assert "LEVERAGED" in html
    assert "3x long Nasdaq-100" in html
    assert "trail 7d +2.5%" in html
    assert "30d after buy +6.5%" in html
    assert "Reddit 7d: 12 posts bullish" in html
    assert "PTR/politician mention" in html


def test_reddit_403_is_not_labeled_sec():
    msg = friendly_feed_error(
        "Client error '403 Forbidden' for url 'https://www.reddit.com/search.json'"
    )
    assert "Reddit blocked" in msg
    assert "SEC" not in msg
