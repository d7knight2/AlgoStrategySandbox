# Telegram Bot Alerts

Real-time alerts to your phone when the research loop finds proposals, risk is paused, or a progress report is generated. Optional **inbound commands** (whitelist chat only).

## Setup (5 minutes)

1. Open Telegram and chat with **@BotFather**
2. `/newbot` → choose a name → copy the **bot token**
3. Start a chat with your bot (press Start)
4. Get your chat id:
   - Message the bot, then open:
     `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Find `"chat":{"id": 123456789}`
   - Or use @userinfobot

5. Add to `/etc/alpaca/env` or `python/.env`:

```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

6. Restart the API:

```bash
systemctl --user restart trading-api.service
```

7. Test outbound:

```bash
curl -X POST http://127.0.0.1:8080/alerts/telegram/test
```

`/health` should show `"telegram_configured": true`.

## Outbound sender (`src/notifications/telegram.py`)

- HTML with plain-text fallback on parse errors
- ~1.05s min interval between sends (flood control)
- Retries on HTTP 429 / 5xx
- Never logs the bot token URL path
- Optional `reply_markup` for URL buttons

## Inbound commands (optional)

Whitelist poller — **only** `TELEGRAM_CHAT_ID` is accepted. No free-text buy/sell.

```bash
cd python
PYTHONPATH=. .venv/bin/python -m src.notifications.bot_commands
```

Or enable the user unit:

```bash
cp deploy/trading-telegram-bot.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now trading-telegram-bot.service
```

| Command | Action |
|---------|--------|
| `/status` `/health` | GET local `:8080/health` |
| `/scan` | POST `/research/scan` propose-only |
| `/pause` `/resume` | Risk kill switch via API |
| `/help` | Command list |

Requires `trading-api.service` on `127.0.0.1:8080`.

## What triggers outbound alerts

| Event | Message |
|-------|--------|
| Research scan | Summary of ALLOW/REJECT proposals |
| Trade proposal ALLOW | Symbol + side + size |
| Risk pause / resume | Kill switch state |
| Progress report | Text summary |
| Daily copy-trade digest | STOCK Act / 13F / research enrichment |
| Manual test | `POST /alerts/telegram/test` |

Weekday timers only for research/copytrade — weekends are quiet unless you `/scan` or send a heartbeat manually.

## Safety

- Alerts are informational; execution still requires RiskEngine ALLOW and paper mode.
- Inbound commands never place buys/sells directly.
- Never put the bot token in git.
