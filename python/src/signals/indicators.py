"""Basic technical indicators — pure functions, no side effects."""

from typing import Any


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    k = 2 / (period + 1)
    ema_val = sum(values[:period]) / period
    for price in values[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_basic_indicators(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute a small set of indicators from OHLCV bars (oldest → newest)."""
    if not bars:
        return {}

    closes = [float(b["close"]) for b in bars]
    volumes = [int(b["volume"]) for b in bars]

    latest = bars[-1]

    return {
        "symbol": latest.get("symbol"),
        "price": closes[-1],
        "sma_20": sma(closes, 20),
        "sma_50": sma(closes, 50),
        "ema_12": ema(closes, 12),
        "ema_26": ema(closes, 26),
        "rsi_14": rsi(closes, 14),
        "volume": volumes[-1],
        "avg_volume_20": sma([float(v) for v in volumes], 20),
        "timestamp": latest.get("timestamp"),
    }
