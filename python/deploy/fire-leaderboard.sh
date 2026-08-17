#!/usr/bin/env bash
# Send paper leaderboard caption + PNG to Telegram (no AI).
set -euo pipefail
ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export TRADING_MODE=paper
export FETCH_PRICES="${FETCH_PRICES:-0}"
.venv/bin/python - <<'PY'
import os
from src.notifications.leaderboard_notify import send_leaderboard_update
fetch = os.environ.get("FETCH_PRICES", "0") == "1"
r = send_leaderboard_update(fetch_prices=fetch, weekly=False)
print(r)
raise SystemExit(0 if r.get("sent") else 1)
PY
