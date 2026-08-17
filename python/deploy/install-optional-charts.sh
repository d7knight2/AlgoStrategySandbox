#!/usr/bin/env bash
# Optional matplotlib + pillow for richer leaderboard PNGs.
set -euo pipefail
ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python"
cd "$ROOT"
.venv/bin/pip install -q 'matplotlib>=3.8' 'pillow>=10.0'
.venv/bin/python -c "import matplotlib, PIL; print('ok', matplotlib.__version__, PIL.__version__)"
