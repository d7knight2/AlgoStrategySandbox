"""Alpaca market data client (Phase 2/3 foundation)."""

from typing import Any
from datetime import datetime, timedelta

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

from src.config import settings


class AlpacaMarketData:
    """Thin wrapper around Alpaca market data API."""

    def __init__(self) -> None:
        settings.validate_credentials()
        self._client = StockHistoricalDataClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )

    def get_latest_quote(self, symbol: str) -> dict[str, Any]:
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quotes = self._client.get_stock_latest_quote(req)
        q = quotes[symbol]
        return {
            "symbol": symbol,
            "bid": float(q.bid_price) if q.bid_price else None,
            "ask": float(q.ask_price) if q.ask_price else None,
            "bid_size": q.bid_size,
            "ask_size": q.ask_size,
            "timestamp": str(q.timestamp),
        }

    def get_bars(
        self,
        symbol: str,
        timeframe: TimeFrame = TimeFrame.Day,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        end = datetime.utcnow()
        start = end - timedelta(days=limit * 2)  # rough window

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            limit=limit,
        )
        bars = self._client.get_stock_bars(req)
        result = []
        for bar in bars[symbol]:
            result.append(
                {
                    "timestamp": str(bar.timestamp),
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": int(bar.volume),
                    "vwap": float(bar.vwap) if bar.vwap else None,
                }
            )
        return result
