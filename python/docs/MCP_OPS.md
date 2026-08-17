# MCP + fleet allowlist for dashboard / Telegram ops

## A) Allowlist patterns (paste into `~/pi-tools/fleet/policy.yml` under `allow:`)

```yaml
  # Trading Core API (localhost only)
  - pattern: '^curl -s http://127\.0\.0\.1:8080/health$'
  - pattern: '^curl -s -X POST http://127\.0\.0\.1:8080/alerts/telegram/test$'
  - pattern: '^curl -s -X POST http://127\.0\.0\.1:8080/research/scan$'
  - pattern: '^curl -s -X POST http://127\.0\.0\.1:8080/risk/(pause|resume)$'
  - pattern: '^curl -s -X POST http://127\.0\.0\.1:8080/reports/generate$'
  - pattern: '^curl -s http://127\.0\.0\.1:8080/portfolio/summary$'
  - pattern: '^curl -s http://127\.0\.0\.1:8080/copytrade/(watchlist|latest)$'
  - pattern: '^curl -s -X POST http://127\.0\.0\.1:8080/copytrade/run$'
  - pattern: '^curl -s -X POST http://127\.0\.0\.1:8080/copytrade/run\?notify=(true|false)$'

  # systemd user service for trading-api
  - pattern: '^systemctl --user (status|is-active|restart|start) trading-api\.service$'
  - pattern: '^systemctl --user (status|is-active|start) trading-report\.service$'
  - pattern: '^systemctl --user (status|is-active|start) trading-copytrade\.service$'
  - pattern: '^systemctl --user (status|is-active|list-timers) trading-.*$'
  - pattern: '^bash /home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/deploy/install-all\.sh$'
  - pattern: '^bash /home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/scripts/run_server\.sh$'

  # logs (read-only)
  - pattern: '^tail -n [0-9]+ /home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/data/reports/(api|cron|research|copytrade)\.log$'
```

After editing policy, **restart the fleet MCP** process that loads `policy.yml`.

## B) Commands Grok can run via PiMCP (once allowlisted)

```bash
# API up?
curl -s http://127.0.0.1:8080/health

# Telegram test
curl -s -X POST http://127.0.0.1:8080/alerts/telegram/test

# Propose-only scan (+ Telegram)
curl -s -X POST http://127.0.0.1:8080/research/scan

# Daily copy-trade digest (Telegram; paper fills only if the timer/env enables execute)
curl -s http://127.0.0.1:8080/copytrade/latest
curl -s -X POST http://127.0.0.1:8080/copytrade/run

# Service
systemctl --user status trading-api.service
systemctl --user restart trading-api.service

# First-time install of units
bash /home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/deploy/install-all.sh
```

## C) Trading-core MCP tools (if that server is connected)

| Tool | Purpose |
|------|--------|
| `api_health` | GET :8080/health |
| `dashboard_url` | Local + Tailscale dashboard links |
| `telegram_debug` | Config check + test send |
| `telegram_test` | Send test message |
| `research_scan_mcp` | Propose-only scan + notify |
| `copytrade_daily` | STOCK Act / 13F digest; `execute=true` is paper-only |
| `risk_pause` / `risk_resume` | Kill switch |

Dashboard “refresh” is automatic via WebSocket (`/ws/live`). Opening the URL is done on your phone; MCP returns the URL via `dashboard_url`.
