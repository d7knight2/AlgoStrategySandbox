"""Unit tests for shared indicator helpers."""

import pandas as pd

from indicators import atr, opening_range, rsi, sma


def test_sma_returns_mean_of_last_n_closes():
    series = pd.Series([1, 2, 3, 4, 5])
    assert sma(series, 3) == 4.0


def test_rsi_detects_oversold_condition():
    series = pd.Series([10, 9, 8, 7, 6, 5, 4, 3, 2, 1])
    assert rsi(series, 2) < 20


def test_atr_is_positive_for_volatile_bars():
    df = pd.DataFrame(
        {
            "high": [11, 12, 13, 14, 15],
            "low": [9, 10, 11, 12, 13],
            "close": [10, 11, 12, 13, 14],
        }
    )
    assert atr(df, 3) > 0


def test_opening_range_extracts_high_low_and_volume():
    df = pd.DataFrame(
        {
            "high": [10, 12, 11],
            "low": [8, 9, 9],
            "volume": [100, 200, 150],
        }
    )
    high, low, avg_volume = opening_range(df, 2)
    assert high == 12
    assert low == 8
    assert avg_volume == 150
