"""Ranked leaderboard of politician paper books + equity series for charts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.copytrade.books import list_book_snapshots, quote_price
from src.database.models import FilerBook, FilerBookFill, FilerBookLot
from src.database.session import SessionLocal


def _book_fill_stats(book_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        fills = (
            db.query(FilerBookFill)
            .filter(FilerBookFill.book_id == book_id)
            .order_by(FilerBookFill.created_at.asc())
            .all()
        )
        buys = sum(1 for f in fills if (f.side or "").lower() == "buy")
        sells = sum(1 for f in fills if (f.side or "").lower() == "sell")
        notional = sum(float(f.notional or 0) for f in fills)
        return {
            "fills": len(fills),
            "buys": buys,
            "sells": sells,
            "notional_traded": round(notional, 2),
            "first_fill": fills[0].created_at.isoformat() if fills else None,
            "last_fill": fills[-1].created_at.isoformat() if fills else None,
        }
    finally:
        db.close()


def ranked_leaderboard(*, fetch_prices: bool = True) -> dict[str, Any]:
    """Leaderboard sorted by paper return_pct (desc)."""
    snaps = list_book_snapshots(fetch_prices=fetch_prices)
    db = SessionLocal()
    try:
        books = {b.filer_key: b for b in db.query(FilerBook).all()}
    finally:
        db.close()

    rows: list[dict[str, Any]] = []
    for s in snaps:
        book = books.get(s["filer"])
        stats = _book_fill_stats(book.id) if book else {}
        rows.append(
            {
                **s,
                **stats,
                "rank": 0,
            }
        )
    rows.sort(key=lambda r: (r.get("return_pct") is None, -(r.get("return_pct") or -1e9)))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(rows),
        "leaderboard": rows,
        "notes": [
            "Virtual paper books only — not politicians' real P&L.",
            "PTRs are delayed (often ~45 days); returns are illustrative.",
            "Ranked by mark-to-market return vs starting_cash.",
        ],
    }


def equity_series_for_filer(filer: str, *, max_points: int = 120) -> dict[str, Any]:
    """Approximate equity curve from virtual fills (cash + open lots marked at fill prices)."""
    db = SessionLocal()
    try:
        book = db.query(FilerBook).filter(FilerBook.filer_key == filer).first()
        if book is None:
            # fuzzy
            all_b = db.query(FilerBook).all()
            hits = [b for b in all_b if filer.lower() in b.filer_key.lower()]
            book = hits[0] if len(hits) == 1 else None
        if book is None:
            return {"error": f"no book for filer={filer}", "series": []}

        fills = (
            db.query(FilerBookFill)
            .filter(FilerBookFill.book_id == book.id)
            .order_by(FilerBookFill.created_at.asc())
            .all()
        )
        cash = float(book.starting_cash)
        lots: dict[str, dict[str, float]] = {}
        series: list[dict[str, Any]] = [
            {
                "t": book.created_at.isoformat() if book.created_at else None,
                "equity": round(cash, 2),
                "cash": round(cash, 2),
            }
        ]

        for f in fills:
            sym = (f.symbol or "").upper()
            side = (f.side or "").lower()
            qty = float(f.qty or 0)
            px = float(f.price or 0)
            if side == "buy" and qty > 0 and px > 0:
                cost = qty * px
                if cost <= cash + 1e-6:
                    cash -= cost
                    lot = lots.setdefault(sym, {"qty": 0.0, "avg": 0.0})
                    new_q = lot["qty"] + qty
                    lot["avg"] = (
                        (lot["avg"] * lot["qty"] + cost) / new_q if new_q else 0.0
                    )
                    lot["qty"] = new_q
            elif side == "sell" and qty > 0 and px > 0:
                lot = lots.get(sym)
                if lot and lot["qty"] > 0:
                    sell_q = min(qty, lot["qty"])
                    cash += sell_q * px
                    lot["qty"] -= sell_q
                    if lot["qty"] <= 1e-9:
                        lots.pop(sym, None)

            mkt = sum(v["qty"] * v["avg"] for v in lots.values())  # cost basis mark
            # Prefer last trade prices for open lots when available
            mkt = 0.0
            for s, v in lots.items():
                mkt += v["qty"] * (px if s == sym and px > 0 else v["avg"])
            equity = cash + mkt
            series.append(
                {
                    "t": f.created_at.isoformat() if f.created_at else None,
                    "equity": round(equity, 2),
                    "cash": round(cash, 2),
                    "symbol": sym,
                    "side": side,
                }
            )

        if len(series) > max_points:
            step = max(1, len(series) // max_points)
            series = series[::step]

        # Mark open lots at live quotes for last point
        live_mkt = 0.0
        for s, v in lots.items():
            q = quote_price(s)
            live_mkt += v["qty"] * (q if q else v["avg"])
        if series:
            series[-1]["equity_marked"] = round(cash + live_mkt, 2)

        return {
            "filer": book.filer_key,
            "starting_cash": float(book.starting_cash),
            "points": len(series),
            "series": series,
        }
    finally:
        db.close()


def multi_equity_series(*, max_filers: int = 8) -> dict[str, Any]:
    """Top filers' equity series for overlay chart."""
    board = ranked_leaderboard(fetch_prices=True)
    top = board["leaderboard"][:max_filers]
    series_map: dict[str, list[dict[str, Any]]] = {}
    for row in top:
        ser = equity_series_for_filer(row["filer"])
        series_map[row["filer"]] = ser.get("series") or []
    return {
        "generated_at": board["generated_at"],
        "filers": [r["filer"] for r in top],
        "leaderboard": top,
        "series": series_map,
        "notes": board["notes"],
    }
