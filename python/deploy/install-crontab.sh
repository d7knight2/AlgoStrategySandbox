#!/usr/bin/env bash
# Fallback: install a user crontab line for the daily report.
set -euo pipefail

ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python"
LINE="5 16 * * 1-5 cd $ROOT && /bin/bash scripts/daily_report.sh >> data/reports/cron.log 2>&1"

mkdir -p "$ROOT/data/reports"
touch "$ROOT/data/reports/cron.log"

# Merge with existing crontab without duplicating
EXISTING="$(crontab -l 2>/dev/null || true)"
if echo "$EXISTING" | grep -Fq "scripts/daily_report.sh"; then
  echo "Crontab entry already present."
else
  (echo "$EXISTING"; echo "$LINE") | grep -v '^$' | crontab -
  echo "Crontab entry added:"
  echo "  $LINE"
fi

echo ""
echo "Current crontab:"
crontab -l
