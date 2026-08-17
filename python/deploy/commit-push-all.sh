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
  python/deploy/*.sh \
  python/deploy/trading-pelosi-weekly.service \
  python/deploy/trading-pelosi-weekly.timer \
  python/deploy/trading-weekly.service \
  python/scripts/patch_leaderboard_telegram.py \
  || true

git status --short
git commit -m "Paper copy rules, leaderboard, skills, deploy helpers" || echo "nothing to commit (sandbox)"
git pull --rebase origin main 2>/dev/null || git pull --no-rebase origin main || true
git push origin main || true
echo "AlgoStrategySandbox push attempted"

# pi-remote fleet policy
PR="/home/d7knight/repos/d7knight2/pi-remote"
if [[ -d "$PR/.git" ]]; then
  cd "$PR"
  git add mcp/fleet/policy.yml scripts/23-sync-fleet-policy.py scripts/24-commit-push-policy.sh 2>/dev/null || true
  git commit -m "Fleet MCP: allow e2e, leaderboard fire, optional charts, commit scripts" || echo "nothing to commit (pi-remote)"
  git pull --rebase origin main 2>/dev/null || git pull --no-rebase origin main || true
  git push origin main || true
  python3 scripts/23-sync-fleet-policy.py 2>/dev/null || true
  systemctl --user restart pi-mcp.service 2>/dev/null || true
  echo "pi-remote push attempted"
fi
