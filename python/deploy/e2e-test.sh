#!/usr/bin/env bash
# Offline-first smoke. Does NOT call live Grok/Gemini/Groq (no quota waste).
# Optional live AI only if E2E_LIVE_AI=1
set -euo pipefail
ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export TRADING_MODE=paper
PY="$ROOT/.venv/bin/python"

echo "[1] Unit tests (mocked AI — no quota)"
$PY -m pytest tests/test_paper_rules_and_ai.py tests/test_config.py tests/test_risk.py tests/test_telegram.py -q --tb=line

echo "[2] Paper rules list"
$PY -c "from src.copytrade.rules import add_rule, list_rules_text; add_rule('Nancy Pelosi', weekly_budget=1000, side='buy'); print(list_rules_text())"

echo "[3] Leaderboard image (no AI)"
$PY -c "from pathlib import Path; from src.copytrade.leaderboard_image import render_leaderboard_png; p=render_leaderboard_png([{'filer':'Pelosi','return_pct':3.2,'equity':10320},{'filer':'Tuberville','return_pct':1.1,'equity':10110}], out_path=Path('data/reports/leaderboard_e2e.png')); print('png', p, p.exists())"

echo "[4] Weekly allocate propose-only"
$PY -m src.copytrade.weekly_allocate --propose-only --no-notify 2>&1 | tail -20

echo "[5] AI key status only (no model call)"
$PY -c "from src.notifications.ai_assist import key_status; print(key_status())"

if [[ "${E2E_LIVE_AI:-0}" == "1" ]]; then
  echo "[6] LIVE AI (E2E_LIVE_AI=1 — uses quota)"
  $PY -c "from src.notifications.ai_assist import ask_ai; r=ask_ai('Reply with exactly: OK paper-only'); print({k:r.get(k) for k in ('ok','provider','error')})"
else
  echo "[6] skip live AI (set E2E_LIVE_AI=1 to enable)"
fi

echo "[7] Telegram configured?"
$PY -c "from src.notifications.telegram import telegram_configured; print('tg', telegram_configured())"

echo "E2E done (no AI quota unless E2E_LIVE_AI=1)"
