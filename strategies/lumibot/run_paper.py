#!/usr/bin/env python3
"""Run a Lumibot strategy against Alpaca paper trading."""

from __future__ import annotations

import argparse
import sys

from lumibot.brokers import Alpaca
from lumibot.traders import Trader

from registry import STRATEGY_REGISTRY, get_strategy_class


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "strategy_id",
        choices=sorted(STRATEGY_REGISTRY),
        help="Strategy catalog id to run",
    )
    parser.add_argument(
        "--benchmark",
        default="SPY",
        help="Benchmark symbol for Lumibot trader",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    strategy_cls = get_strategy_class(args.strategy_id)

    broker = Alpaca({"API_KEY": None, "API_SECRET": None, "PAPER": True})
    strategy = strategy_cls(broker=broker)
    trader = Trader()
    trader.add_strategy(strategy)
    trader.run_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
