# Deploy on Raspberry Pi

## One-shot install (API + report + research + copy-trade timers)

```bash
cd ~/repos/d7knight2/AlgoStrategySandbox/python
bash deploy/install-all.sh
sudo loginctl enable-linger "$USER"   # keep user services after logout
```

## What gets installed

| Unit | Purpose |
|------|--------|
| `trading-api.service` | FastAPI + dashboard on **:8080** (survives reboot) |
| `trading-report.timer` | Weekday 16:05 progress report (+ email if configured) |
| `trading-research.timer` | Weekday 09:45 / 12:30 / 15:45 signal scan (propose only) |
| `trading-copytrade.timer` | Weekday 17:00 STOCK Act / 13F digest + paper copy (see `docs/COPYTRADE.md`) |

## URLs (via Tailscale)

- Health: `http://<tailscale-ip>:8080/health`
- Dashboard: `http://<tailscale-ip>:8080/dashboard`

## Secrets

Prefer group-readable system file:

```bash
sudo chgrp "$USER" /etc/alpaca/env
sudo chmod 640 /etc/alpaca/env
```

Or project `.env` (never commit):

```bash
# python/.env
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
TRADING_MODE=paper
```

Optional email for reports: `REPORT_EMAIL_TO`, `SMTP_*` in the same env file.

## Safety

- Research timer runs **propose only** (no `--execute`).
- Copy-trade timer submits **Alpaca paper** orders only after RiskEngine ALLOW (`--execute`, $100 cap).
- API still forces `TRADING_MODE=paper`.
- Kill switch: dashboard **STOP** or `POST /risk/pause`.

## Logs

```bash
tail -f data/reports/api.log
tail -f data/reports/cron.log
tail -f data/reports/research.log
tail -f data/reports/copytrade.log
```
