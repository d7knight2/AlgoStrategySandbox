"""Alpaca market data client (Phase 2/3 foundation).

Free / paper accounts must use the IEX feed. Requesting SIP (default on some
endpoints when end≈now) returns:
  subscription does not permit querying recent SIP data
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

from src.config import settings


class AlpacaMarketData:
    """Thin wrapper around Alpaca market data API (IEX feed for free tier)."""

    def __init__(self) -> None:
        settings.validate_credentials()
        self._client = StockHistoricalDataClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )

    def get_latest_quote(self, symbol: str) -> dict[str, Any]:
        req = StockLatestQuoteRequest(
            symbol_or_symbols=symbol,
            feed=DataFeed.IEX,
        )
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
        # Timezone-aware UTC; end slightly in the past so free-tier IEX works
        # without triggering SIP recent-data 403.
        end = datetime.now(timezone.utc) - timedelta(minutes=20)
        start = end - timedelta(days=max(limit * 2, 30))

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            limit=limit,
            feed=DataFeed.IEX,
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
