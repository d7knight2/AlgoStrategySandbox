#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python"
UNIT="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
cd "$ROOT"

# Prefer generalized weekly allocate over pelosi-only
cat > "$ROOT/deploy/trading-allocate-weekly.service" << 'EOF'
[Unit]
Description=Weekly paper allocate for all copy rules
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python
Environment=PYTHONPATH=/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python
Environment=TRADING_MODE=paper
ExecStart=/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/.venv/bin/python -m src.copytrade.weekly_allocate
StandardOutput=append:/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/data/reports/allocate-weekly.log
StandardError=append:/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/data/reports/allocate-weekly.log
EOF

cat > "$ROOT/deploy/trading-allocate-weekly.timer" << 'EOF'
[Unit]
Description=Sunday weekly paper allocate all rules

[Timer]
OnCalendar=Sun 10:15:00
Persistent=true
Unit=trading-allocate-weekly.service

[Install]
WantedBy=timers.target
EOF

python3 << 'PY'
from pathlib import Path
p = Path("/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/src/notifications/commands.py")
t = p.read_text()
if "cmd_rules" in t and "/ai" in t:
    print("commands already have rules/ai")
else:
    t = t.replace(
        "/book Pelosi\n\nNo live trading",
        "/book Pelosi\n/leaderboard\n"
        "/rules · /rule Pelosi 1000 buy\n"
        "/allocate [propose] — run paper copy rules now\n"
        "/ai [question] — Grok/Gemini analysis (optional keys)\n\n"
        "No live trading",
        1,
    )
    t = t.replace(
        'if cmd in {"/leaderboard", "/lb"}:',
        'if cmd in {"/rules", "/rule"}:\n'
        '        from src.notifications.cmd_rules import cmd_rule, cmd_rules\n'
        '        return cmd_rules(arg) if cmd == "/rules" else cmd_rule(arg)\n'
        '    if cmd == "/allocate":\n'
        '        from src.notifications.cmd_rules import cmd_allocate\n'
        '        return cmd_allocate(arg)\n'
        '    if cmd == "/ai":\n'
        '        from src.notifications.cmd_rules import cmd_ai\n'
        '        return cmd_ai(arg)\n'
        '    if cmd in {"/leaderboard", "/lb"}:',
        1,
    )
    # if leaderboard not present, inject before /books
    if "cmd_rules" not in t:
        t = t.replace(
            'if cmd == "/books":\n        return _cmd_books()',
            'if cmd in {"/rules", "/rule"}:\n'
            '        from src.notifications.cmd_rules import cmd_rule, cmd_rules\n'
            '        return cmd_rules(arg) if cmd == "/rules" else cmd_rule(arg)\n'
            '    if cmd == "/allocate":\n'
            '        from src.notifications.cmd_rules import cmd_allocate\n'
            '        return cmd_allocate(arg)\n'
            '    if cmd == "/ai":\n'
            '        from src.notifications.cmd_rules import cmd_ai\n'
            '        return cmd_ai(arg)\n'
            '    if cmd == "/books":\n        return _cmd_books()',
            1,
        )
    p.write_text(t)
    print("commands patched")
PY

mkdir -p "$UNIT" "$ROOT/data/reports"
cp "$ROOT/deploy/trading-allocate-weekly.service" "$UNIT/"
cp "$ROOT/deploy/trading-allocate-weekly.timer" "$UNIT/"
touch "$ROOT/data/reports/allocate-weekly.log"
systemctl --user daemon-reload
systemctl --user enable --now trading-allocate-weekly.timer
systemctl --user restart trading-telegram.service 2>/dev/null || true
echo "Done. Telegram: /rule Pelosi 1000 buy · /rules · /allocate · /ai"
echo "Optional AI: export XAI_API_KEY=... or GEMINI_API_KEY=... in /etc/alpaca/env"
