"""SMA regime rotation strategy template for Lumibot + Alpaca paper trading."""

from lumibot.strategies.strategy import Strategy


class SmaRegimeRotationStrategy(Strategy):
    """Rotate allocation based on SPY trend regime."""

    parameters = {
        "risk_on": ["SPY", "QQQ"],
        "risk_off": ["SHY", "IEF"],
        "lookback": 200,
    }

    def initialize(self):
        self.sleeptime = "24H"

    def on_trading_iteration(self):
        spy_prices = self.get_historical_prices("SPY", self.parameters["lookback"], "day")
        if spy_prices is None or len(spy_prices.df) < self.parameters["lookback"]:
            return

        close_series = spy_prices.df["close"]
        sma = float(close_series.mean())
        latest_close = float(close_series.iloc[-1])

        targets = self.parameters["risk_on"] if latest_close > sma else self.parameters["risk_off"]
        weight = 1 / len(targets)

        self.sell_all()
        for symbol in targets:
            self.create_order(symbol, weight, "buy", quote="percent")
