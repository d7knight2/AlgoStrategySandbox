---
name: paper-copy-ops
description: Operate AlgoStrategySandbox paper copy rules, weekly allocate, Telegram leaderboard images, and offline tests. Use for /rule /rules /allocate /leaderboard, Pelosi weekly budget, e2e-test, fleet MCP policy, LibreChat AI keys without burning quota in unit tests.
---

# Paper copy ops (Telegram + fleet)

## Safety

- Paper only. Live trading stays disabled.
- Unit tests never call Grok/Gemini/Groq (skill `unit-test-writing`).
- AI analysis is optional (`/ai`, LibreChat `GOOGLE_KEY` / `GROQ_API_KEY`, `grok` CLI).

## Telegram commands

| Command | Purpose |
|---------|---------|
| `/rule Name 1000 buy` | Paper weekly budget rule |
| `/rules` | List rules |
| `/allocate` / `/allocate propose` | Run rules now |
| `/leaderboard` | Ranked paper books + image |
| `/track Name` | Virtual book |
| `/ai …` | Optional analysis (uses quota) |

## Deploy scripts

```bash
bash python/deploy/apply-rules-ai-bot.sh
bash python/deploy/apply-leaderboard-bot.sh
bash python/deploy/e2e-test.sh          # no AI quota
bash python/deploy/fire-leaderboard.sh  # send Telegram update
```

## Fleet MCP

Allowlisted run_command patterns live in `pi-remote/mcp/fleet/policy.yml`.
Sync live policy: `python3 pi-remote/scripts/23-sync-fleet-policy.py` then restart `pi-mcp.service`.

## Leaderboard send

```python
from src.notifications.leaderboard_notify import send_leaderboard_update
send_leaderboard_update(fetch_prices=False)  # offline-friendly
```

Optional prettier PNG: `pip install matplotlib pillow` in the project venv.
