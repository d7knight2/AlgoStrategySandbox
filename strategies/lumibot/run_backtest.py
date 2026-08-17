#!/usr/bin/env python3
"""Run a Lumibot backtest for a registered strategy."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from lumibot.backtesting import YahooDataBacktesting

from registry import STRATEGY_REGISTRY, get_strategy_class


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "strategy_id",
        choices=sorted(STRATEGY_REGISTRY),
        help="Strategy catalog id to backtest",
    )
    parser.add_argument("--start", default="2023-01-01", help="Backtest start date")
    parser.add_argument("--end", default="2024-01-01", help="Backtest end date")
    parser.add_argument(
        "--budget",
        type=float,
        default=100_000.0,
        help="Starting cash budget",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    strategy_cls = get_strategy_class(args.strategy_id)

    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end)

    results = strategy_cls.run_backtest(
        YahooDataBacktesting,
        start,
        end,
        budget=args.budget,
    )
    print(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
