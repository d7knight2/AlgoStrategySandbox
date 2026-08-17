"""Technical indicators — pure functions, no side effects.

Uses pure-Python SMA/EMA/RSI by default. When pandas-ta is installed, also
computes MACD, ATR, and Bollinger mid for richer research (optional fields).
"""

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


def _pandas_ta_extras(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Optional MACD / ATR / Bollinger via pandas-ta (fail soft)."""
    try:
        import pandas as pd
        import pandas_ta as ta
    except Exception:
        return {}

    if len(bars) < 30:
        return {}

    try:
        df = pd.DataFrame(
            {
                "open": [float(b["open"]) for b in bars],
                "high": [float(b["high"]) for b in bars],
                "low": [float(b["low"]) for b in bars],
                "close": [float(b["close"]) for b in bars],
                "volume": [float(b["volume"]) for b in bars],
            }
        )
        out: dict[str, Any] = {"engine": "pandas-ta"}
        macd = ta.macd(df["close"])
        if macd is not None and not macd.empty:
            last = macd.iloc[-1]
            out["macd"] = float(last.iloc[0]) if pd.notna(last.iloc[0]) else None
            out["macd_signal"] = (
                float(last.iloc[2]) if len(last) > 2 and pd.notna(last.iloc[2]) else None
            )
            out["macd_hist"] = (
                float(last.iloc[1]) if len(last) > 1 and pd.notna(last.iloc[1]) else None
            )
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)
        if atr is not None and len(atr) and pd.notna(atr.iloc[-1]):
            out["atr_14"] = float(atr.iloc[-1])
        bb = ta.bbands(df["close"], length=20)
        if bb is not None and not bb.empty:
            row = bb.iloc[-1]
            # Column order varies by version; take first/mid/last if present
            vals = [float(x) for x in row.tolist() if pd.notna(x)]
            if len(vals) >= 3:
                out["bb_lower"], out["bb_mid"], out["bb_upper"] = vals[0], vals[1], vals[2]
        return out
    except Exception:
        return {}


def compute_basic_indicators(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute core indicators from OHLCV bars (oldest → newest)."""
    if not bars:
        return {}

    closes = [float(b["close"]) for b in bars]
    volumes = [int(b["volume"]) for b in bars]
    latest = bars[-1]

    result: dict[str, Any] = {
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
    result.update(_pandas_ta_extras(bars))
    return result
