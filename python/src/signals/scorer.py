"""Deterministic signal scoring (Phase 4 foundation).

Produces a normalized score and a simple BUY/SELL/HOLD decision.
This is intentionally transparent and non-AI so it can be backtested cleanly.
"""

from typing import Any


def score_from_indicators(indicators: dict[str, Any]) -> dict[str, Any]:
    """Compute a simple weighted signal score from basic indicators.

    Returns:
        {
            "decision": "BUY" | "SELL" | "HOLD",
            "signal_score": float,          # roughly -1 .. +1
            "confidence": float,            # 0 .. 1
            "components": {...},
            "reasoning": str,
        }
    """
    price = indicators.get("price")
    sma20 = indicators.get("sma_20")
    sma50 = indicators.get("sma_50")
    rsi = indicators.get("rsi_14")
    volume = indicators.get("volume")
    avg_vol = indicators.get("avg_volume_20")

    components: dict[str, float] = {}
    reasons: list[str] = []

    # Trend component
    trend = 0.0
    if price is not None and sma20 is not None and sma50 is not None:
        if price > sma20 > sma50:
            trend = 0.6
            reasons.append("Price above SMA20 > SMA50 (uptrend)")
        elif price < sma20 < sma50:
            trend = -0.6
            reasons.append("Price below SMA20 < SMA50 (downtrend)")
        elif price > sma20:
            trend = 0.2
            reasons.append("Price above SMA20")
        elif price < sma20:
            trend = -0.2
            reasons.append("Price below SMA20")
    components["trend"] = trend

    # Momentum / RSI component
    momentum = 0.0
    if rsi is not None:
        if rsi < 30:
            momentum = 0.5
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 70:
            momentum = -0.5
            reasons.append(f"RSI overbought ({rsi:.1f})")
        elif rsi < 45:
            momentum = 0.2
        elif rsi > 55:
            momentum = -0.2
    components["momentum"] = momentum

    # Volume confirmation
    volume_score = 0.0
    if volume is not None and avg_vol is not None and avg_vol > 0:
        ratio = volume / avg_vol
        if ratio > 1.5:
            volume_score = 0.3 if trend >= 0 else -0.3
            reasons.append(f"Volume {ratio:.1f}x average")
        elif ratio < 0.7:
            volume_score = -0.1
            reasons.append("Below-average volume")
    components["volume"] = volume_score

    # Weighted combination (simple, tunable later)
    signal_score = (
        0.50 * components.get("trend", 0.0)
        + 0.35 * components.get("momentum", 0.0)
        + 0.15 * components.get("volume", 0.0)
    )

    # Decision thresholds (conservative)
    if signal_score >= 0.35:
        decision = "BUY"
    elif signal_score <= -0.35:
        decision = "SELL"
    else:
        decision = "HOLD"

    confidence = min(1.0, abs(signal_score) / 0.7)

    return {
        "decision": decision,
        "signal_score": round(signal_score, 4),
        "confidence": round(confidence, 4),
        "components": components,
        "reasoning": "; ".join(reasons) if reasons else "Neutral / insufficient data",
    }
