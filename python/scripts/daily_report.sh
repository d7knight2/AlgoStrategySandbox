#!/usr/bin/env bash
# Generate progress report and email if SMTP is configured.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
python -c "
from src.reporting import generate_progress_report, send_report_email
r = generate_progress_report()
print(r['summary'])
e = send_report_email(r)
print('email:', e)
"
