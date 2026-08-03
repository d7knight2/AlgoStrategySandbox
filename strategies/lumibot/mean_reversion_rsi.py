"""RSI mean reversion basket strategy for Lumibot + Alpaca paper trading."""

from __future__ import annotations

from lumibot.strategies.strategy import Strategy

from indicators import atr, rsi, sma
from risk import position_size_by_risk, split_take_profit_quantities


class RsiMeanReversionStrategy(Strategy):
    """Buy oversold names in an uptrend and scale out on mean reversion."""

    parameters = {
        "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        "rsi_period": 2,
        "rsi_threshold": 10,
        "sma_period": 50,
        "atr_period": 14,
        "min_avg_volume": 2_000_000,
        "risk_fraction": 0.01,
        "stop_atr_multiple": 2.0,
        "tp1_atr_multiple": 1.0,
        "tp2_atr_multiple": 2.0,
    }

    def initialize(self):
        self.sleeptime = "1D"
        self.tracked_positions: dict[str, dict[str, float | int]] = {}

    def on_trading_iteration(self):
        for symbol in self.parameters["symbols"]:
            self._evaluate_symbol(symbol)

    def _evaluate_symbol(self, symbol: str) -> None:
        lookback = max(
            self.parameters["sma_period"],
            self.parameters["atr_period"] + 1,
            self.parameters["rsi_period"] + 1,
        )
        bars = self.get_historical_prices(symbol, lookback + 5, "day")
        if bars is None or len(bars.df) < lookback:
            return

        df = bars.df
        close_series = df["close"]
        latest_close = float(close_series.iloc[-1])
        rsi_value = rsi(close_series, self.parameters["rsi_period"])
        sma_value = sma(close_series, self.parameters["sma_period"])
        atr_value = atr(df, self.parameters["atr_period"])

        if "volume" in df.columns:
            avg_volume = float(df["volume"].iloc[-20:].mean())
            if avg_volume < self.parameters["min_avg_volume"]:
                return

        position = self.get_position(symbol)
        tracked = self.tracked_positions.get(symbol)

        if position is not None and position.quantity != 0 and tracked:
            self._manage_open_position(symbol, latest_close, float(atr_value), tracked)
            return

        if position is not None and position.quantity != 0:
            return

        if rsi_value >= self.parameters["rsi_threshold"]:
            return
        if latest_close <= sma_value:
            return

        stop_price = latest_close - (
            float(atr_value) * self.parameters["stop_atr_multiple"]
        )
        cash = self.get_cash()
        qty = position_size_by_risk(
            cash, self.parameters["risk_fraction"], latest_close, stop_price
        )
        if qty <= 0:
            return

        order = self.create_order(symbol, qty, "buy")
        self.submit_order(order)
        tp1_qty, tp2_qty = split_take_profit_quantities(qty)
        self.tracked_positions[symbol] = {
            "entry": latest_close,
            "stop": stop_price,
            "tp1": latest_close
            + float(atr_value) * self.parameters["tp1_atr_multiple"],
            "tp2": latest_close
            + float(atr_value) * self.parameters["tp2_atr_multiple"],
            "tp1_qty": tp1_qty,
            "tp2_qty": tp2_qty,
            "tp1_hit": 0,
        }

    def _manage_open_position(
        self,
        symbol: str,
        current_price: float,
        atr_value: float,
        tracked: dict[str, float | int],
    ) -> None:
        stop_price = float(tracked["stop"])
        if current_price <= stop_price:
            self._exit_symbol(symbol)
            return

        position = self.get_position(symbol)
        if position is None or position.quantity == 0:
            self.tracked_positions.pop(symbol, None)
            return

        if not tracked.get("tp1_hit") and current_price >= float(tracked["tp1"]):
            qty = int(tracked["tp1_qty"])
            if qty > 0:
                order = self.create_order(symbol, qty, "sell")
                self.submit_order(order)
            tracked["tp1_hit"] = 1
            tracked["stop"] = float(tracked["entry"])

        if current_price >= float(tracked["tp2"]):
            self._exit_symbol(symbol)

    def _exit_symbol(self, symbol: str) -> None:
        position = self.get_position(symbol)
        if position is not None and position.quantity != 0:
            order = self.create_order(symbol, position.quantity, "sell")
            self.submit_order(order)
        self.tracked_positions.pop(symbol, None)
