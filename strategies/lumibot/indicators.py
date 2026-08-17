"""Shared indicator helpers for Lumibot strategy templates."""

from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, period: int) -> float:
    if len(series) < period:
        return float("nan")
    return float(series.iloc[-period:].mean())


def rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return float("nan")

    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.iloc[-period:].mean()
    avg_loss = loss.iloc[-period:].mean()

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def atr(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < period + 1:
        return float("nan")

    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return float(true_range.iloc[-period:].mean())


def opening_range(
    df: pd.DataFrame, minutes: int
) -> tuple[float, float, float]:
    window = df.iloc[:minutes]
    range_high = float(window["high"].max())
    range_low = float(window["low"].min())
    avg_volume = (
        float(window["volume"].mean()) if "volume" in window.columns else 0.0
    )
    return range_high, range_low, avg_volume
