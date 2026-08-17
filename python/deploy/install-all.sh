#!/usr/bin/env bash
# Install Trading Core user services: API, daily report, research scan, copy-trade digest,
# Telegram command poller, weekly funds recap.
set -euo pipefail

ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$UNIT_DIR" "$ROOT/data/reports"

# Ensure venv exists
if [[ ! -x "$ROOT/.venv/bin/uvicorn" ]]; then
  echo "Creating venv and installing deps…"
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
fi

cp "$ROOT/deploy/trading-api.service" "$UNIT_DIR/"
cp "$ROOT/deploy/trading-report.service" "$UNIT_DIR/"
cp "$ROOT/deploy/trading-report.timer" "$UNIT_DIR/"
cp "$ROOT/deploy/trading-research.service" "$UNIT_DIR/"
cp "$ROOT/deploy/trading-research.timer" "$UNIT_DIR/"
cp "$ROOT/deploy/trading-copytrade.service" "$UNIT_DIR/"
cp "$ROOT/deploy/trading-copytrade.timer" "$UNIT_DIR/"
cp "$ROOT/deploy/trading-telegram-bot.service" "$UNIT_DIR/"
cp "$ROOT/deploy/trading-telegram.service" "$UNIT_DIR/"
cp "$ROOT/deploy/trading-weekly.service" "$UNIT_DIR/"
cp "$ROOT/deploy/trading-weekly.timer" "$UNIT_DIR/"

touch "$ROOT/data/reports/api.log" "$ROOT/data/reports/cron.log" \
  "$ROOT/data/reports/research.log" "$ROOT/data/reports/copytrade.log" \
  "$ROOT/data/reports/telegram.log" "$ROOT/data/reports/telegram-bot.log" "$ROOT/data/reports/weekly.log"

systemctl --user daemon-reload
systemctl --user enable --now trading-api.service
systemctl --user enable --now trading-report.timer
systemctl --user enable --now trading-research.timer
systemctl --user enable --now trading-copytrade.timer
systemctl --user disable --now trading-telegram.service 2>/dev/null || true
systemctl --user enable --now trading-telegram-bot.service
systemctl --user enable --now trading-weekly.timer

echo ""
echo "=== Services ==="
systemctl --user status trading-api.service --no-pager || true
echo ""
echo "=== Timers ==="
systemctl --user list-timers 'trading-*' --no-pager || true
echo ""
echo "Dashboard: http://$(tailscale ip -4 2>/dev/null || echo '<pi-ip>'):8080/dashboard"
echo ""
echo "If timers stop after logout:"
echo "  sudo loginctl enable-linger $(whoami)"
echo ""
echo "Manual tests:"
echo "  systemctl --user restart trading-api.service"
echo "  systemctl --user start trading-report.service"
echo "  systemctl --user start trading-research.service"
echo "  systemctl --user start trading-copytrade.service"
echo "  systemctl --user restart trading-telegram-bot.service"
echo "  systemctl --user start trading-weekly.service"
