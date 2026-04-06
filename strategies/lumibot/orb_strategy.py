"""Opening Range Breakout strategy template for Lumibot + Alpaca paper trading."""

from lumibot.strategies.strategy import Strategy


class OpeningRangeBreakoutStrategy(Strategy):
    """Trade breakout of first session range with simple risk controls."""

    parameters = {
        "symbol": "SPY",
        "opening_minutes": 30,
        "risk_fraction": 0.01,
    }

    def initialize(self):
        self.sleeptime = "1M"
        self.range_high = None
        self.range_low = None
        self.has_position = False

    def on_trading_iteration(self):
        bars = self.get_historical_prices(self.parameters["symbol"], 60, "minute")
        if bars is None or len(bars.df) < self.parameters["opening_minutes"]:
            return

        opening_window = bars.df.iloc[: self.parameters["opening_minutes"]]
        self.range_high = float(opening_window["high"].max())
        self.range_low = float(opening_window["low"].min())

        current_price = self.get_last_price(self.parameters["symbol"])
        if current_price is None or self.has_position:
            return

        if current_price > self.range_high:
            cash = self.get_cash()
            risk_capital = cash * self.parameters["risk_fraction"]
            stop_distance = max(current_price - self.range_low, 0.01)
            qty = int(risk_capital / stop_distance)
            if qty > 0:
                order = self.create_order(self.parameters["symbol"], qty, "buy")
                self.submit_order(order)
                self.has_position = True
