#!/usr/bin/env bash
# Paper research loop — propose only by default.
# Add --execute to submit risk-approved paper orders.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
python -m src.research.loop "$@"
