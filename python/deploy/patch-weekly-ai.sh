#!/usr/bin/env bash
# Wire weekly.py to use AI-enriched Telegram package.
set -euo pipefail
ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python"
python3 << 'PY'
from pathlib import Path
p = Path("/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/src/reporting/weekly.py")
t = p.read_text()
if "send_weekly_package" in t:
    print("weekly already AI-wired")
else:
    # Prefer replacing simple send_telegram of weekly body if we find notify block
    if "from src.notifications import send_telegram" in t:
        t = t.replace(
            "from src.notifications import send_telegram",
            "from src.notifications import send_telegram\n"
            "from src.reporting.weekly_notify import send_weekly_package",
            1,
        )
    # After report dict is mostly built, before final notify — inject helper call
    # Look for typical pattern: report["telegram"] = send_telegram(
    if 'report["telegram"] = send_telegram' in t:
        t = t.replace(
            'report["telegram"] = send_telegram',
            'report["telegram"] = send_weekly_package(report, body_html=format_weekly_html(report))  # patched\n    _UNUSED = send_telegram',
            1,
        )
        # That may break if format_weekly_html missing — use safer approach below
    # Safer: append import and replace notify section with explicit block via marker
    if "send_weekly_package(report" not in t or "_UNUSED" in t:
        # undo bad patch
        t = t.replace(
            'report["telegram"] = send_weekly_package(report, body_html=format_weekly_html(report))  # patched\n    _UNUSED = send_telegram',
            'report["telegram"] = send_telegram',
            1,
        )
        # Find format function name
        fmt = "format_weekly_report" if "def format_weekly_report" in t else None
        if fmt is None and "def format_wee" in t:
            import re
            m = re.search(r"def (format_wee\w+)", t)
            fmt = m.group(1) if m else None
        if fmt:
            needle = f'report["telegram"] = send_telegram({fmt}'
            # try multiline patterns
            import re
            t2, n = re.subn(
                r'report\["telegram"\]\s*=\s*send_telegram\(\s*' + fmt + r'\(report\)\s*\)',
                'report["telegram"] = send_weekly_package(report, body_html=' + fmt + '(report))',
                t,
                count=1,
            )
            if n:
                t = t2
                print("wired send_weekly_package via", fmt)
            else:
                # looser: any send_telegram after notify and weekly_on
                t2, n = re.subn(
                    r'(if notify and weekly_on:[^\n]*\n\s*)report\["telegram"\]\s*=\s*send_telegram\(([^\)]+)\)',
                    r'\1report["telegram"] = send_weekly_package(report, body_html=\2)',
                    t,
                    count=1,
                    flags=re.S,
                )
                if n:
                    t = t2
                    print("wired send_weekly_package loose")
                else:
                    print("could not auto-wire; manual edit needed")
        else:
            print("format function not found")
    p.write_text(t)
    print("done")
PY
echo "Optional env in /etc/alpaca/env:"
echo "  WEEKLY_AI=1"
echo "  WEEKLY_AI_IMAGE=1"
echo "  XAI_API_KEY=...   # or GROK_API_KEY"
echo "  GEMINI_API_KEY=..."
