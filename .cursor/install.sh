#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for AlgoStrategySandbox.
# Prepares both the Next.js frontend (repo root) and the Python FastAPI
# trading core (python/). Safe to run repeatedly and against cached state.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

echo "==> Installing system packages (python venv support)"
py_mm="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
sudo apt-get update -qq
# Match the default python3 (3.12, 3.13, …). python3.12-venv fails on images
# whose python3 is a different minor version.
if ! sudo apt-get install -y -qq "python${py_mm}-venv"; then
  sudo apt-get install -y -qq python3-venv
fi

echo "==> Installing frontend dependencies (npm ci)"
npm ci

echo "==> Installing Playwright Chromium + system dependencies"
npx playwright install --with-deps chromium

echo "==> Setting up Python trading core (python/.venv)"
cd "$repo_root/python"
if [ ! -x ".venv/bin/python" ] || ! .venv/bin/python -c 'import sys' 2>/dev/null; then
  rm -rf .venv
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
# httpx is required by the FastAPI TestClient / test suite; ruff for lint checks.
pip install -q httpx ruff

echo "==> Install complete"
