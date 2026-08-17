# Dashboard & Progress Reports

## Safari Web App (iPhone / iPad)

1. Start the server on the Pi (reachable from your phone — Tailscale or LAN):
   ```bash
   cd ~/repos/d7knight2/AlgoStrategySandbox/python
   source .venv/bin/activate
   uvicorn src.main:app --host 0.0.0.0 --port 8000
   ```
2. On iPhone Safari open: `http://<pi-tailscale-ip>:8000/dashboard`
3. Share → **Add to Home Screen**
4. It opens standalone (no Safari chrome) thanks to:
   - `apple-mobile-web-app-capable`
   - Web App Manifest (`/static/manifest.json`)
   - Light service worker for shell caching

## Progress reports

| Endpoint | Purpose |
|----------|--------|
| `GET /reports/latest` | Last generated report JSON |
| `POST /reports/generate` | Build report now (+ email if configured) |
| Dashboard **Send report** button | Same as generate |

CLI / cron:
```bash
bash scripts/daily_report.sh
```

Example crontab (weekdays 4:05 PM PT ≈ after US close):
```cron
5 16 * * 1-5 cd /home/d7knight/repos/d7knight2/AlgoStrategySandbox/python && bash scripts/daily_report.sh >> data/reports/cron.log 2>&1
```

## Email setup (optional)

Add to `/etc/alpaca/env` or process environment:

```bash
REPORT_EMAIL_TO=you@example.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@example.com
SMTP_PASSWORD=app-password
SMTP_FROM=you@example.com
```

If SMTP is not set, reports are still saved under `python/data/reports/` and shown on the dashboard.
