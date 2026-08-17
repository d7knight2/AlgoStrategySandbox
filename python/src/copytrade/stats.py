"""7d / 30d price stats around a disclosed government-official buy/sell.

Uses Alpaca daily bars when credentials work. Pure helpers are unit-tested
without the network.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.feeds.congress import _parse_date


def parse_bar_time(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    text = str(raw).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        return _parse_date(text[:10])


def parse_event_date(trade: dict[str, Any]) -> datetime | None:
    for key in ("transaction_date", "disclosure_date"):
        dt = _parse_date(str(trade.get(key) or "") or None)
        if dt is not None:
            return dt
    return None


def _close_on_or_after(bars: list[dict[str, Any]], target: datetime) -> dict[str, Any] | None:
    for bar in bars:
        ts = parse_bar_time(bar.get("timestamp"))
        if ts is not None and ts.date() >= target.date() and float(bar.get("close") or 0) > 0:
            return bar
    return None


def _close_on_or_before(bars: list[dict[str, Any]], target: datetime) -> dict[str, Any] | None:
    picked: dict[str, Any] | None = None
    for bar in bars:
        ts = parse_bar_time(bar.get("timestamp"))
        if ts is not None and ts.date() <= target.date() and float(bar.get("close") or 0) > 0:
            picked = bar
    return picked


def _pct(start: float, end: float) -> float | None:
    if start <= 0 or end <= 0:
        return None
    return round((end / start - 1.0) * 100.0, 2)


def trailing_return_pct(bars: list[dict[str, Any]], days: int) -> float | None:
    if len(bars) < 2:
        return None
    last = bars[-1]
    last_ts = parse_bar_time(last.get("timestamp"))
    last_close = float(last.get("close") or 0)
    if last_ts is None or last_close <= 0:
        return None
    start = _close_on_or_after(bars, last_ts - timedelta(days=days))
    if start is None:
        start = bars[0]
    return _pct(float(start.get("close") or 0), last_close)


def mean_volume(bars: list[dict[str, Any]], days: int) -> float | None:
    if not bars:
        return None
    last_ts = parse_bar_time(bars[-1].get("timestamp"))
    if last_ts is None:
        return None
    cutoff = last_ts - timedelta(days=days)
    vols = [
        float(b.get("volume") or 0)
        for b in bars
        if (ts := parse_bar_time(b.get("timestamp"))) is not None and ts >= cutoff
    ]
    if not vols:
        return None
    return round(sum(vols) / len(vols), 0)


def forward_return_pct(bars: list[dict[str, Any]], start: datetime, days: int) -> float | None:
    """Percent change from the first bar on/after `start` to `start+days`."""
    entry = _close_on_or_after(bars, start)
    if entry is None:
        entry = _close_on_or_before(bars, start)
    if entry is None:
        return None
    end = _close_on_or_after(bars, start + timedelta(days=days))
    if end is None:
        return None
    return _pct(float(entry.get("close") or 0), float(end.get("close") or 0))


def since_event_pct(bars: list[dict[str, Any]], start: datetime) -> float | None:
    entry = _close_on_or_after(bars, start) or _close_on_or_before(bars, start)
    if entry is None or not bars:
        return None
    return _pct(float(entry.get("close") or 0), float(bars[-1].get("close") or 0))


def price_stats(
    bars: list[dict[str, Any]],
    *,
    event_date: datetime | None = None,
    side: str | None = None,
) -> dict[str, Any]:
    """Trailing 7d/30d plus post-disclosure 7d/30d when the buy date is old enough."""
    if not bars:
        return {"ok": False, "error": "no bars"}
    last = bars[-1]
    last_close = float(last.get("close") or 0)
    out: dict[str, Any] = {
        "ok": True,
        "last": round(last_close, 4) if last_close else None,
        "as_of": str(last.get("timestamp") or ""),
        "ret_7d_pct": trailing_return_pct(bars, 7),
        "ret_30d_pct": trailing_return_pct(bars, 30),
        "avg_vol_7d": mean_volume(bars, 7),
        "avg_vol_30d": mean_volume(bars, 30),
        "event_date": event_date.date().isoformat() if event_date else None,
        "side": side,
        "since_event_pct": None,
        "fwd_7d_pct": None,
        "fwd_30d_pct": None,
        "fwd_7d_ready": False,
        "fwd_30d_ready": False,
    }
    vol7 = out["avg_vol_7d"]
    vol30 = out["avg_vol_30d"]
    if vol7 and vol30 and vol30 > 0:
        out["vol_7d_vs_30d"] = round(vol7 / vol30, 2)
    else:
        out["vol_7d_vs_30d"] = None

    if event_date is not None:
        out["since_event_pct"] = since_event_pct(bars, event_date)
        last_ts = parse_bar_time(last.get("timestamp"))
        if last_ts is not None:
            out["fwd_7d_ready"] = last_ts.date() >= (event_date + timedelta(days=7)).date()
            out["fwd_30d_ready"] = last_ts.date() >= (event_date + timedelta(days=30)).date()
        if out["fwd_7d_ready"]:
            out["fwd_7d_pct"] = forward_return_pct(bars, event_date, 7)
        if out["fwd_30d_ready"]:
            out["fwd_30d_pct"] = forward_return_pct(bars, event_date, 30)
    return out
