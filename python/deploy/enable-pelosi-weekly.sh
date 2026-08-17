#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python"
UNIT="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$UNIT" "$ROOT/data/reports"
cp "$ROOT/deploy/trading-pelosi-weekly.service" "$UNIT/"
cp "$ROOT/deploy/trading-pelosi-weekly.timer" "$UNIT/"
touch "$ROOT/data/reports/pelosi-weekly.log"
systemctl --user daemon-reload
systemctl --user enable --now trading-pelosi-weekly.timer
echo "Enabled trading-pelosi-weekly.timer (Sun 10:15)"
systemctl --user list-timers 'trading-pelosi*' --no-pager || true
echo "Manual run:"
echo "  cd $ROOT && PYTHONPATH=. .venv/bin/python -m src.copytrade.weekly_pelosi"
echo "Propose only:"
echo "  PYTHONPATH=. .venv/bin/python -m src.copytrade.weekly_pelosi --propose-only"
