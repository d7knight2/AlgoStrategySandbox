"""SMA regime rotation strategy template for Lumibot + Alpaca paper trading."""

from __future__ import annotations

from datetime import datetime

from lumibot.strategies.strategy import Strategy

from indicators import sma
from risk import capped_weight


class SmaRegimeRotationStrategy(Strategy):
    """Rotate allocation based on SPY trend regime with monthly rebalance."""

    parameters = {
        "risk_on": ["SPY", "QQQ"],
        "risk_off": ["SHY", "IEF"],
        "lookback": 200,
        "max_allocation_per_asset": 0.30,
    }

    def initialize(self):
        self.sleeptime = "24H"
        self.last_rebalance_month: int | None = None
        self.active_regime: str | None = None

    def on_trading_iteration(self):
        now = datetime.now()
        if (
            self.last_rebalance_month == now.month
            and self.active_regime is not None
        ):
            return

        spy_prices = self.get_historical_prices("SPY", self.parameters["lookback"], "day")
        if spy_prices is None or len(spy_prices.df) < self.parameters["lookback"]:
            return

        close_series = spy_prices.df["close"]
        sma_value = sma(close_series, self.parameters["lookback"])
        latest_close = float(close_series.iloc[-1])

        regime = "risk_on" if latest_close > sma_value else "risk_off"
        if regime == self.active_regime and self.last_rebalance_month == now.month:
            return

        targets = (
            self.parameters["risk_on"]
            if regime == "risk_on"
            else self.parameters["risk_off"]
        )
        raw_weight = 1 / len(targets)
        weight = capped_weight(
            raw_weight, self.parameters["max_allocation_per_asset"]
        )

        self.sell_all()
        for symbol in targets:
            self.create_order(symbol, weight, "buy", quote="percent")

        self.active_regime = regime
        self.last_rebalance_month = now.month
