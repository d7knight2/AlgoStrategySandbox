"""Virtual paper books that track one politician's public STOCK Act flow.

Alpaca still has a single paper account. Each book is a ledger (cash + lots)
marked to market for Telegram stats. Optional auto_execute also submits the
shared Alpaca paper account after RiskEngine ALLOW.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.config import settings
from src.database.models import FilerBook, FilerBookFill, FilerBookLot
from src.database.session import SessionLocal

log = logging.getLogger("trading_core.copytrade.books")

DEFAULT_CASH = 10_000.0


def _norm_filer(name: str) -> str:
    return " ".join((name or "").split()).strip()


def tracked_filer_names() -> list[str]:
    db = SessionLocal()
    try:
        rows = db.query(FilerBook).filter(FilerBook.enabled.is_(True)).all()
        return [r.filer_key for r in rows]
    finally:
        db.close()


def books_matching(filer: str) -> list[dict[str, Any]]:
    hay = (filer or "").lower()
    db = SessionLocal()
    try:
        out: list[dict[str, Any]] = []
        for row in db.query(FilerBook).filter(FilerBook.enabled.is_(True)).all():
            key = row.filer_key.lower()
            if key and (key in hay or hay in key):
                out.append(
                    {
                        "id": row.id,
                        "filer_key": row.filer_key,
                        "auto_execute": row.auto_execute,
                    }
                )
        return out
    finally:
        db.close()


def any_book_wants_execute(filer: str) -> bool:
    return any(b["auto_execute"] for b in books_matching(filer))


def create_book(
    filer: str,
    *,
    starting_cash: float = DEFAULT_CASH,
    auto_execute: bool = True,
) -> dict[str, Any]:
    name = _norm_filer(filer)
    if len(name) < 3:
        return {"ok": False, "error": "Need a politician name (e.g. Pelosi)"}
    cash = max(100.0, float(starting_cash))
    db = SessionLocal()
    try:
        row = db.query(FilerBook).filter(FilerBook.filer_key == name).first()
        if row is None:
            row = FilerBook(
                filer_key=name,
                enabled=True,
                auto_execute=auto_execute,
                starting_cash=cash,
                cash=cash,
            )
            db.add(row)
            created = True
        else:
            row.enabled = True
            row.auto_execute = auto_execute
            created = False
        db.commit()
        db.refresh(row)
        return {
            "ok": True,
            "created": created,
            "filer": row.filer_key,
            "starting_cash": row.starting_cash,
            "cash": row.cash,
            "auto_execute": row.auto_execute,
            "book_id": row.id,
        }
    finally:
        db.close()


def disable_book(filer: str) -> dict[str, Any]:
    name = _norm_filer(filer)
    db = SessionLocal()
    try:
        row = _find_book(db, name)
        if row is None:
            return {"ok": False, "error": f"No paper book for {name}"}
        row.enabled = False
        db.commit()
        return {"ok": True, "filer": row.filer_key, "enabled": False}
    finally:
        db.close()


def _find_book(db, name: str) -> FilerBook | None:
    needle = name.lower()
    rows = db.query(FilerBook).all()
    exact = [r for r in rows if r.filer_key.lower() == needle]
    if exact:
        return exact[0]
    partial = [r for r in rows if needle in r.filer_key.lower() or r.filer_key.lower() in needle]
    return partial[0] if len(partial) == 1 else None


def apply_virtual_fill(
    trade: dict[str, Any],
    *,
    price: float,
    notional_cap: float | None = None,
    via: str = "virtual",
) -> list[dict[str, Any]]:
    """Apply a PTR to every matching enabled book. No Alpaca call."""
    cap = float(notional_cap if notional_cap is not None else settings.copytrade_max_notional)
    if price <= 0:
        return [{"ok": False, "error": "no price"}]
    filer = str(trade.get("watchlist_match") or trade.get("filer") or "")
    matches = books_matching(filer)
    if not matches:
        return []
    out: list[dict[str, Any]] = []
    db = SessionLocal()
    try:
        for meta in matches:
            book = db.get(FilerBook, meta["id"])
            if book is None or not book.enabled:
                continue
            event_key = str(trade.get("event_key") or "")
            if event_key:
                dup = (
                    db.query(FilerBookFill)
                    .filter(
                        FilerBookFill.book_id == book.id,
                        FilerBookFill.event_key == event_key,
                    )
                    .first()
                )
                if dup is not None:
                    out.append({"ok": True, "skipped": "already in book", "filer": book.filer_key})
                    continue
            result = _apply_one(db, book, trade, price=price, cap=cap, via=via)
            out.append(result)
        db.commit()
    finally:
        db.close()
    return out


def _apply_one(
    db,
    book: FilerBook,
    trade: dict[str, Any],
    *,
    price: float,
    cap: float,
    via: str,
) -> dict[str, Any]:
    symbol = str(trade.get("symbol") or "").upper()
    side = str(trade.get("side") or "").lower()
    lot = (
        db.query(FilerBookLot)
        .filter(FilerBookLot.book_id == book.id, FilerBookLot.symbol == symbol)
        .first()
    )
    if lot is None:
        lot = FilerBookLot(book_id=book.id, symbol=symbol, qty=0.0, avg_price=0.0)
        db.add(lot)
        db.flush()

    if side == "buy":
        spend = min(cap, float(book.cash))
        if spend < 1:
            return {"ok": False, "filer": book.filer_key, "error": "book cash empty"}
        qty = spend / price
        new_qty = float(lot.qty) + qty
        if new_qty > 0:
            lot.avg_price = (float(lot.qty) * float(lot.avg_price) + spend) / new_qty
        lot.qty = new_qty
        book.cash = float(book.cash) - spend
        notional = spend
    elif side == "sell":
        if float(lot.qty) <= 0:
            return {
                "ok": False,
                "filer": book.filer_key,
                "error": "no long to sell",
                "symbol": symbol,
            }
        qty = float(lot.qty)
        notional = qty * price
        book.cash = float(book.cash) + notional
        lot.qty = 0.0
    else:
        return {"ok": False, "error": f"unsupported side {side}"}

    lot.updated_at = datetime.utcnow()
    db.add(
        FilerBookFill(
            book_id=book.id,
            event_key=str(trade.get("event_key") or ""),
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            notional=notional,
            via=via,
        )
    )
    return {
        "ok": True,
        "filer": book.filer_key,
        "symbol": symbol,
        "side": side,
        "qty": round(qty, 6),
        "price": price,
        "notional": round(notional, 2),
        "cash": round(float(book.cash), 2),
    }


def quote_price(symbol: str) -> float | None:
    try:
        from src.market_data import AlpacaMarketData

        q = AlpacaMarketData().get_latest_quote(symbol)
        bid = float(q.get("bid") or 0)
        ask = float(q.get("ask") or 0)
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        if ask > 0:
            return ask
        if bid > 0:
            return bid
    except Exception as exc:
        log.warning("quote failed symbol=%s error=%s", symbol, exc)
    try:
        from src.market_data import AlpacaMarketData

        bars = AlpacaMarketData().get_bars(symbol, limit=5)
        if bars:
            return float(bars[-1]["close"])
    except Exception as exc:
        log.warning("bars fallback failed symbol=%s error=%s", symbol, exc)
    return None


def mark_book(
    book: FilerBook, lots: list[FilerBookLot], prices: dict[str, float]
) -> dict[str, Any]:
    positions = []
    mkt = 0.0
    for lot in lots:
        if float(lot.qty) <= 0:
            continue
        px = prices.get(lot.symbol)
        value = float(lot.qty) * px if px else None
        if value is not None:
            mkt += value
        positions.append(
            {
                "symbol": lot.symbol,
                "qty": round(float(lot.qty), 6),
                "avg_price": round(float(lot.avg_price), 4),
                "last": px,
                "market_value": round(value, 2) if value is not None else None,
            }
        )
    equity = float(book.cash) + mkt
    start = float(book.starting_cash) or 1.0
    return {
        "filer": book.filer_key,
        "enabled": book.enabled,
        "auto_execute": book.auto_execute,
        "starting_cash": round(start, 2),
        "cash": round(float(book.cash), 2),
        "positions": positions,
        "equity": round(equity, 2),
        "return_pct": round((equity / start - 1.0) * 100.0, 2),
    }


def list_book_snapshots(*, fetch_prices: bool = True) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        books = db.query(FilerBook).order_by(FilerBook.filer_key).all()
        lots_by: dict[int, list[FilerBookLot]] = {}
        symbols: set[str] = set()
        for b in books:
            lots = db.query(FilerBookLot).filter(FilerBookLot.book_id == b.id).all()
            lots_by[b.id] = lots
            for lot in lots:
                if float(lot.qty) > 0:
                    symbols.add(lot.symbol)
        prices: dict[str, float] = {}
        if fetch_prices:
            for sym in symbols:
                px = quote_price(sym)
                if px:
                    prices[sym] = px
        return [mark_book(b, lots_by.get(b.id, []), prices) for b in books]
    finally:
        db.close()


def book_snapshot(filer: str, *, fetch_prices: bool = True) -> dict[str, Any] | None:
    snaps = list_book_snapshots(fetch_prices=fetch_prices)
    needle = filer.lower()
    hits = [s for s in snaps if needle in s["filer"].lower() or s["filer"].lower() in needle]
    if len(hits) == 1:
        return hits[0]
    exact = [s for s in snaps if s["filer"].lower() == needle]
    return exact[0] if exact else None
