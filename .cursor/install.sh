#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for AlgoStrategySandbox.
# Prepares both the Next.js frontend (repo root) and the Python FastAPI
# trading core (python/). Safe to run repeatedly and against cached state.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

echo "==> Installing system packages (python venv support)"
sudo apt-get update -qq
sudo apt-get install -y -qq python3.12-venv

echo "==> Installing frontend dependencies (npm ci)"
npm ci

echo "==> Installing Playwright Chromium + system dependencies"
npx playwright install --with-deps chromium

echo "==> Setting up Python trading core (python/.venv)"
cd "$repo_root/python"
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
# httpx is required by the FastAPI TestClient / test suite; ruff for lint checks.
pip install -q httpx ruff

echo "==> Install complete"
