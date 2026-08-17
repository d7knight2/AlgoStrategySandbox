"""Opening Range Breakout strategy template for Lumibot + Alpaca paper trading."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from lumibot.strategies.strategy import Strategy

from indicators import opening_range
from risk import position_size_by_risk

ET = ZoneInfo("America/New_York")
ENTRY_CUTOFF = time(14, 30)


class OpeningRangeBreakoutStrategy(Strategy):
    """Trade breakout of first session range with volume confirmation and risk controls."""

    parameters = {
        "symbol": "SPY",
        "opening_minutes": 30,
        "risk_fraction": 0.01,
        "volume_multiplier": 1.2,
    }

    def initialize(self):
        self.sleeptime = "1M"
        self.range_high = None
        self.range_low = None
        self.opening_avg_volume = 0.0
        self.entry_side: str | None = None
        self.stop_price: float | None = None

    def on_trading_iteration(self):
        if self._is_past_entry_cutoff():
            self._manage_open_position()
            return

        bars = self.get_historical_prices(self.parameters["symbol"], 60, "minute")
        if bars is None or len(bars.df) < self.parameters["opening_minutes"]:
            return

        self.range_high, self.range_low, self.opening_avg_volume = opening_range(
            bars.df, self.parameters["opening_minutes"]
        )

        current_price = self.get_last_price(self.parameters["symbol"])
        if current_price is None:
            return

        position = self.get_position(self.parameters["symbol"])
        if position is not None and position.quantity != 0:
            self._manage_open_position(current_price)
            return

        latest_volume = float(bars.df.iloc[-1].get("volume", 0))
        volume_confirmed = (
            self.opening_avg_volume == 0
            or latest_volume
            >= self.opening_avg_volume * self.parameters["volume_multiplier"]
        )
        if not volume_confirmed:
            return

        if current_price > self.range_high:
            self._enter_position("long", current_price)
        elif current_price < self.range_low:
            self._enter_position("short", current_price)

    def _enter_position(self, side: str, current_price: float) -> None:
        cash = self.get_cash()
        if side == "long":
            stop = self.range_low
            qty = position_size_by_risk(
                cash, self.parameters["risk_fraction"], current_price, stop
            )
            if qty <= 0:
                return
            order = self.create_order(self.parameters["symbol"], qty, "buy")
            self.entry_side = "long"
            self.stop_price = stop
        else:
            stop = self.range_high
            qty = position_size_by_risk(
                cash, self.parameters["risk_fraction"], current_price, stop
            )
            if qty <= 0:
                return
            order = self.create_order(self.parameters["symbol"], qty, "sell")
            self.entry_side = "short"
            self.stop_price = stop

        self.submit_order(order)

    def _manage_open_position(self, current_price: float | None = None) -> None:
        position = self.get_position(self.parameters["symbol"])
        if position is None or position.quantity == 0:
            self.entry_side = None
            self.stop_price = None
            return

        if current_price is None:
            current_price = self.get_last_price(self.parameters["symbol"])
        if current_price is None or self.stop_price is None or self.entry_side is None:
            return

        hit_stop = (
            self.entry_side == "long" and current_price <= self.stop_price
        ) or (self.entry_side == "short" and current_price >= self.stop_price)

        if hit_stop or self._is_past_entry_cutoff():
            side = "sell" if position.quantity > 0 else "buy"
            order = self.create_order(
                self.parameters["symbol"], abs(position.quantity), side
            )
            self.submit_order(order)
            self.entry_side = None
            self.stop_price = None

    def _is_past_entry_cutoff(self) -> bool:
        now = datetime.now(ET)
        return now.time() >= ENTRY_CUTOFF
