"""Classify tickers as common stock vs leveraged / inverse products.

Politicians sometimes disclose 2x/3x ETFs (TQQQ, SOXL, NVDL, …). Paper copies
still use the $100 cap; this is so the digest can say what the name *is*.
"""

from __future__ import annotations

import re
from typing import Any

# Popular 2x/3x and inverse ETFs. Factor is the advertised daily leverage.
# underlying is a short human label, not a tradable hedge.
_CATALOG: dict[str, dict[str, Any]] = {
    # Index / mega
    "TQQQ": {"factor": 3, "direction": "long", "underlying": "Nasdaq-100"},
    "SQQQ": {"factor": 3, "direction": "short", "underlying": "Nasdaq-100"},
    "QLD": {"factor": 2, "direction": "long", "underlying": "Nasdaq-100"},
    "QID": {"factor": 2, "direction": "short", "underlying": "Nasdaq-100"},
    "UPRO": {"factor": 3, "direction": "long", "underlying": "S&P 500"},
    "SPXU": {"factor": 3, "direction": "short", "underlying": "S&P 500"},
    "SPXL": {"factor": 3, "direction": "long", "underlying": "S&P 500"},
    "SPXS": {"factor": 3, "direction": "short", "underlying": "S&P 500"},
    "SSO": {"factor": 2, "direction": "long", "underlying": "S&P 500"},
    "SDS": {"factor": 2, "direction": "short", "underlying": "S&P 500"},
    "SH": {"factor": 1, "direction": "short", "underlying": "S&P 500"},
    "PSQ": {"factor": 1, "direction": "short", "underlying": "Nasdaq-100"},
    "TNA": {"factor": 3, "direction": "long", "underlying": "Russell 2000"},
    "TZA": {"factor": 3, "direction": "short", "underlying": "Russell 2000"},
    "UDOW": {"factor": 3, "direction": "long", "underlying": "Dow 30"},
    "SDOW": {"factor": 3, "direction": "short", "underlying": "Dow 30"},
    # Sector
    "SOXL": {"factor": 3, "direction": "long", "underlying": "semiconductors"},
    "SOXS": {"factor": 3, "direction": "short", "underlying": "semiconductors"},
    "TECL": {"factor": 3, "direction": "long", "underlying": "technology"},
    "TECS": {"factor": 3, "direction": "short", "underlying": "technology"},
    "FAS": {"factor": 3, "direction": "long", "underlying": "financials"},
    "FAZ": {"factor": 3, "direction": "short", "underlying": "financials"},
    "LABU": {"factor": 3, "direction": "long", "underlying": "biotech"},
    "LABD": {"factor": 3, "direction": "short", "underlying": "biotech"},
    "CURE": {"factor": 3, "direction": "long", "underlying": "healthcare"},
    "DFEN": {"factor": 3, "direction": "long", "underlying": "defense"},
    "NAIL": {"factor": 3, "direction": "long", "underlying": "homebuilders"},
    "WANT": {"factor": 3, "direction": "long", "underlying": "consumer discretionary"},
    "WEBS": {"factor": 3, "direction": "short", "underlying": "consumer discretionary"},
    "FNGU": {"factor": 3, "direction": "long", "underlying": "FANG+"},
    "FNGD": {"factor": 3, "direction": "short", "underlying": "FANG+"},
    "YINN": {"factor": 3, "direction": "long", "underlying": "China"},
    "YANG": {"factor": 3, "direction": "short", "underlying": "China"},
    # Commodities / rates / vol
    "BOIL": {"factor": 2, "direction": "long", "underlying": "natural gas"},
    "KOLD": {"factor": 2, "direction": "short", "underlying": "natural gas"},
    "AGQ": {"factor": 2, "direction": "long", "underlying": "silver"},
    "UCO": {"factor": 2, "direction": "long", "underlying": "crude oil"},
    "SCO": {"factor": 2, "direction": "short", "underlying": "crude oil"},
    "TMF": {"factor": 3, "direction": "long", "underlying": "20+ year Treasuries"},
    "TBT": {"factor": 2, "direction": "short", "underlying": "20+ year Treasuries"},
    "UVXY": {"factor": 1.5, "direction": "long", "underlying": "VIX short-term"},
    "SVXY": {"factor": 0.5, "direction": "short", "underlying": "VIX short-term"},
    # Single-stock 2x (GraniteShares / T-Rex / Direxion / YieldMax-adjacent bulls)
    "NVDL": {"factor": 2, "direction": "long", "underlying": "NVDA"},
    "NVDX": {"factor": 2, "direction": "long", "underlying": "NVDA"},
    "NVDQ": {"factor": 2, "direction": "short", "underlying": "NVDA"},
    "TSLL": {"factor": 2, "direction": "long", "underlying": "TSLA"},
    "TSLQ": {"factor": 2, "direction": "short", "underlying": "TSLA"},
    "CONL": {"factor": 2, "direction": "long", "underlying": "COIN"},
    "AMDL": {"factor": 2, "direction": "long", "underlying": "AMD"},
    "AMZU": {"factor": 2, "direction": "long", "underlying": "AMZN"},
    "AAPU": {"factor": 2, "direction": "long", "underlying": "AAPL"},
    "GGLL": {"factor": 2, "direction": "long", "underlying": "GOOGL"},
    "MSFX": {"factor": 2, "direction": "long", "underlying": "MSFT"},
    "MSTU": {"factor": 2, "direction": "long", "underlying": "MSTR"},
    "MSTX": {"factor": 2, "direction": "long", "underlying": "MSTR"},
    "MSTZ": {"factor": 2, "direction": "short", "underlying": "MSTR"},
    "PTIR": {"factor": 2, "direction": "long", "underlying": "PLTR"},
    "BITX": {"factor": 2, "direction": "long", "underlying": "Bitcoin"},
    "ETHU": {"factor": 2, "direction": "long", "underlying": "Ether"},
}

_LEV_NAME = re.compile(
    r"\b(2X|3X|1\.5X|ULTRAPRO|ULTRA PRO|DIREXION DAILY|GRANITESHARES|BULL 2X|BULL 3X)\b",
    re.I,
)
_INV_NAME = re.compile(r"\b(BEAR|INVERSE|ULTRASHORT|ULTRA SHORT|-1X|SHORT 2X|SHORT 3X)\b", re.I)
_COVERED = re.compile(r"\b(COVERED CALL|OPTION INCOME|YIELDMAX|SYNTHETIC COVERED)\b", re.I)


def classify_instrument(symbol: str, name: str = "") -> dict[str, Any]:
    """Return leverage / product type for a disclosed ticker."""
    sym = (symbol or "").upper().strip()
    hay = f"{sym} {name}".strip()
    known = _CATALOG.get(sym)
    if known:
        factor = float(known["factor"])
        direction = str(known["direction"])
        underlying = str(known["underlying"])
        leveraged = factor >= 1.5 or direction == "short"
        label = _label(factor, direction, underlying)
        return {
            "symbol": sym,
            "name": name or label,
            "leveraged": leveraged,
            "factor": factor,
            "direction": direction,
            "underlying": underlying,
            "kind": "leveraged_etf" if leveraged else "etf",
            "label": label,
            "matched": "catalog",
        }

    if _COVERED.search(hay):
        return {
            "symbol": sym,
            "name": name or sym,
            "leveraged": False,
            "factor": 1.0,
            "direction": "long",
            "underlying": "",
            "kind": "covered_call_etf",
            "label": "covered-call / option-income ETF (not leveraged)",
            "matched": "name",
        }

    direction = "short" if _INV_NAME.search(hay) else "long"
    factor: float | None = None
    if re.search(r"\b3X\b", hay, re.I) or "ULTRAPRO" in hay.upper():
        factor = 3.0
    elif (
        re.search(r"\b2X\b", hay, re.I)
        or re.search(r"\bULTRA\b", hay, re.I)
        or _LEV_NAME.search(hay)
    ):
        factor = 2.0
    elif direction == "short":
        factor = 1.0

    if factor is not None:
        leveraged = factor >= 1.5 or direction == "short"
        label = _label(factor, direction, name or "index/stock")
        return {
            "symbol": sym,
            "name": name or sym,
            "leveraged": leveraged,
            "factor": factor,
            "direction": direction,
            "underlying": name or "",
            "kind": "leveraged_etf" if leveraged else "inverse_etf",
            "label": label,
            "matched": "name",
        }

    return {
        "symbol": sym,
        "name": name or sym,
        "leveraged": False,
        "factor": 1.0,
        "direction": "long",
        "underlying": "",
        "kind": "common_stock",
        "label": (name or "common stock / ETF").strip()[:80] or "common stock / ETF",
        "matched": "default",
    }


def _label(factor: float, direction: str, underlying: str) -> str:
    side = "long" if direction == "long" else "inverse/short"
    u = (underlying or "underlying").strip()
    fx = str(int(factor)) if factor == int(factor) else str(factor)
    return f"{fx}x {side} {u}"
