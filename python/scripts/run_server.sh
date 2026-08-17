#!/usr/bin/env bash
# Run Trading Core API + dashboard (default port 8080 — 8000 is often PiMCP).
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
PORT="${PORT:-8080}"
echo "Starting Trading Core on 0.0.0.0:${PORT}"
echo "Dashboard: http://$(tailscale ip -4 2>/dev/null || echo '<pi-ip>'):${PORT}/dashboard"
exec uvicorn src.main:app --host 0.0.0.0 --port "$PORT"
