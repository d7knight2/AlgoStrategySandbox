#!/usr/bin/env bash
# Install systemd user timer for daily progress reports.
set -euo pipefail

ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$UNIT_DIR" "$ROOT/data/reports"

cp "$ROOT/deploy/trading-report.service" "$UNIT_DIR/"
cp "$ROOT/deploy/trading-report.timer" "$UNIT_DIR/"

# Ensure log file exists
touch "$ROOT/data/reports/cron.log"

systemctl --user daemon-reload
systemctl --user enable --now trading-report.timer
systemctl --user status trading-report.timer --no-pager || true

echo ""
echo "Installed. Next runs:"
systemctl --user list-timers trading-report.timer --no-pager || true
echo ""
echo "Test now with:"
echo "  systemctl --user start trading-report.service"
echo "  tail -50 $ROOT/data/reports/cron.log"
