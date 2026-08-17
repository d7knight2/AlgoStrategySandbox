"""CLI: daily STOCK Act / 13F digest + optional paper copy."""

from __future__ import annotations

import argparse
import json
import logging

from src.copytrade.engine import run_copytrade_daily


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Daily public-disclosure digest (paper only)")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Submit Alpaca PAPER orders after RiskEngine ALLOW (still not live)",
    )
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--lookback-days", type=int, default=None)
    parser.add_argument("--max-notional", type=float, default=None)
    args = parser.parse_args()
    report = run_copytrade_daily(
        execute=True if args.execute else None,
        notify=not args.no_notify,
        lookback_days=args.lookback_days,
        max_notional=args.max_notional,
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
