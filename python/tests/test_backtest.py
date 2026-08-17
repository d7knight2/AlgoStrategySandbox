"""Backtest engine tests."""

from src.backtest.engine import simple_backtest


def _make_bars(n: int = 80, start: float = 100.0) -> list[dict]:
    bars = []
    price = start
    for i in range(n):
        # mild uptrend with noise
        price = price * (1.001 if i % 3 else 0.999)
        bars.append(
            {
                "timestamp": f"2024-01-{(i % 28) + 1:02d}",
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 1_000_000 + i * 1000,
            }
        )
    return bars


def test_backtest_runs():
    bars = _make_bars(100)
    result = simple_backtest(bars, initial_cash=10_000.0)
    assert "error" not in result
    assert result["final_equity"] > 0
    assert "total_return_pct" in result
    assert isinstance(result["trades"], list)


def test_backtest_insufficient_bars():
    result = simple_backtest(_make_bars(30))
    assert "error" in result
