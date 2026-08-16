"""Signal scorer tests."""

from src.signals.scorer import score_from_indicators


def test_buy_signal_on_uptrend_oversold():
    indicators = {
        "price": 100.0,
        "sma_20": 98.0,
        "sma_50": 95.0,
        "rsi_14": 28.0,
        "volume": 2_000_000,
        "avg_volume_20": 1_000_000,
    }
    result = score_from_indicators(indicators)
    assert result["decision"] in ("BUY", "HOLD")
    assert result["signal_score"] > 0


def test_sell_signal_on_downtrend_overbought():
    indicators = {
        "price": 90.0,
        "sma_20": 95.0,
        "sma_50": 100.0,
        "rsi_14": 75.0,
        "volume": 2_000_000,
        "avg_volume_20": 1_000_000,
    }
    result = score_from_indicators(indicators)
    assert result["decision"] in ("SELL", "HOLD")
    assert result["signal_score"] < 0


def test_neutral_when_missing_data():
    result = score_from_indicators({})
    assert result["decision"] == "HOLD"
