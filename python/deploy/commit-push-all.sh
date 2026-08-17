#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox"
cd "$ROOT"

git add \
  .cursor/skills/unit-test-writing \
  .cursor/skills/paper-copy-ops \
  .cursor/rules \
  python/pytest.ini \
  python/requirements.txt \
  python/tests/conftest.py \
  python/tests/test_paper_rules_and_ai.py \
  python/tests/test_leaderboard_image.py \
  python/tests/test_dashboard_playwright.py \
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
  python/deploy/commit-push-e2e.sh \
  python/deploy/commit-push-all.sh \
  python/deploy/e2e-test.sh \
  python/deploy/enable-pelosi-weekly.sh \
  python/deploy/fire-leaderboard.sh \
  python/deploy/install-optional-charts.sh \
  python/deploy/patch-weekly-ai.sh \
  python/deploy/trading-pelosi-weekly.service \
  python/deploy/trading-pelosi-weekly.timer \
  python/deploy/trading-weekly.service \
  python/deploy/install-all.sh \
  python/scripts/patch_leaderboard_telegram.py \
  || true

git status --short
git commit -m "Paper copy rules, leaderboard Telegram, unit-test no-AI skill, optional charts" || echo "nothing to commit"
git pull --rebase origin main || git pull --no-rebase origin main
git push origin main
echo "AlgoStrategySandbox pushed"
