#!/usr/bin/env bash
# Wire /leaderboard into commands.py + weekly leaderboard photo + deps.
set -euo pipefail
ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python"
cd "$ROOT"

.venv/bin/pip install -q matplotlib pillow || true

python3 << 'PY'
from pathlib import Path
ROOT = Path("/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python")

# --- commands.py ---
p = ROOT / "src/notifications/commands.py"
t = p.read_text()
if "cmd_leaderboard" not in t:
    t = t.replace(
        "/books\n/book Pelosi",
        "/books\n/book Pelosi\n/leaderboard — ranked paper books + chart image",
        1,
    )
    t = t.replace(
        'if cmd == "/books":\n        return _cmd_books()',
        'if cmd in {"/leaderboard", "/lb"}:\n        from src.notifications.cmd_leaderboard import cmd_leaderboard\n'
        '        return cmd_leaderboard()\n'
        '    if cmd == "/books":\n        return _cmd_books()',
        1,
    )
    t = t.replace(
        'if "status" in lower or "health" in lower or "equity" in lower:\n        return "/status"',
        'if "leaderboard" in lower or lower in {"lb", "ranks", "ranking"}:\n        return "/leaderboard"\n'
        '    if "status" in lower or "health" in lower or "equity" in lower:\n        return "/status"',
        1,
    )
    p.write_text(t)
    print("commands patched")
else:
    print("commands already patched")

# --- weekly.py ---
p = ROOT / "src/reporting/weekly.py"
t = p.read_text()
if "send_leaderboard_update" not in t:
    hook = '''
    # Leaderboard chart (weekly image update)
    try:
        from src.notifications.leaderboard_notify import send_leaderboard_update

        if notify and weekly_on:
            report["leaderboard_telegram"] = send_leaderboard_update(
                fetch_prices=True, weekly=True
            )
    except Exception as _lb_exc:
        log.warning("weekly leaderboard image failed: %s", type(_lb_exc).__name__)
        report["leaderboard_telegram"] = {"sent": False, "error": type(_lb_exc).__name__}

'''
    idx = t.rfind("return report")
    if idx >= 0:
        t = t[:idx] + hook + "    " + t[idx:]
        p.write_text(t)
        print("weekly patched")
    else:
        print("weekly: return report not found")
else:
    print("weekly already patched")
PY

systemctl --user restart trading-telegram.service 2>/dev/null || true
echo "Done. Try /leaderboard in Telegram. Weekly image goes out with trading-weekly.timer (Sun 10:00)."
