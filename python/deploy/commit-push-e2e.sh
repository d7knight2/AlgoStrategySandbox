#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox"
cd "$ROOT"

git add \
  python/src/copytrade/rules.py \
  python/src/copytrade/weekly_allocate.py \
  python/src/copytrade/weekly_pelosi.py \
  python/src/copytrade/leaderboard_image.py \
  python/src/notifications/ai_assist.py \
  python/src/notifications/cmd_rules.py \
  python/src/notifications/cmd_leaderboard.py \
  python/src/notifications/leaderboard_notify.py \
  python/src/notifications/photo.py \
  python/src/reporting/weekly_ai.py \
  python/src/reporting/weekly_job.py \
  python/src/reporting/weekly_notify.py \
  python/deploy/apply-leaderboard-bot.sh \
  python/deploy/apply-rules-ai-bot.sh \
  python/deploy/enable-pelosi-weekly.sh \
  python/deploy/patch-weekly-ai.sh \
  python/deploy/trading-pelosi-weekly.service \
  python/deploy/trading-pelosi-weekly.timer \
  python/deploy/trading-weekly.service \
  python/deploy/install-all.sh \
  python/scripts/patch_leaderboard_telegram.py \
  python/deploy/commit-push-e2e.sh \
  python/deploy/e2e-test.sh 2>/dev/null || true

git status --short
git commit -m "Paper copy rules, weekly allocate, leaderboard images, LibreChat AI for Telegram" || echo "nothing to commit"
git push origin main

echo "=== e2e tests ==="
bash "$ROOT/python/deploy/e2e-test.sh"
