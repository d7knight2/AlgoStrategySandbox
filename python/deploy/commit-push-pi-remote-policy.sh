#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/d7knight/repos/d7knight2/pi-remote"
cd "$ROOT"
git add mcp/fleet/policy.yml scripts/23-sync-fleet-policy.py scripts/24-commit-push-policy.sh
git status --short
git commit -m "Fleet MCP: allow e2e, leaderboard fire, optional charts, commit scripts" || echo "nothing to commit"
git pull --rebase origin main 2>/dev/null || git pull --no-rebase origin main || true
git push origin main
if [[ -f scripts/23-sync-fleet-policy.py ]]; then
  python3 scripts/23-sync-fleet-policy.py || true
fi
systemctl --user restart pi-mcp.service 2>/dev/null || true
echo "pi-remote policy pushed"
