# Telegram Bot Alerts

Real-time alerts to your phone when the research loop finds proposals, risk is paused, or a progress report is generated.

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
# or
bash scripts/run_server.sh
```

7. Test:

```bash
curl -X POST http://127.0.0.1:8080/alerts/telegram/test
```

You should get a Telegram message. `/health` will show `"telegram_configured": true`.

## What triggers alerts

| Event | Message |
|-------|--------|
| Research scan | Summary of ALLOW/REJECT proposals |
| Trade proposal ALLOW | Symbol + side + size |
| Risk pause / resume | Kill switch state |
| Progress report | Text summary |
| Manual test | `POST /alerts/telegram/test` |

## Safety

- Alerts are informational only.
- Execution still requires RiskEngine ALLOW and paper mode.
- Never put the bot token in git.
