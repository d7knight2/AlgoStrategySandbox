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

  # systemd user service for trading-api
  - pattern: '^systemctl --user (status|is-active|restart|start) trading-api\.service$'
  - pattern: '^systemctl --user (status|is-active|start) trading-report\.service$'
  - pattern: '^systemctl --user (status|is-active|list-timers) trading-.*$'
  - pattern: '^bash /home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/deploy/install-all\.sh$'
  - pattern: '^bash /home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/scripts/run_server\.sh$'

  # logs (read-only)
  - pattern: '^tail -n [0-9]+ /home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/data/reports/(api|cron|research|mcp)\.log$'
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

# Service
systemctl --user status trading-api.service
systemctl --user restart trading-api.service

# First-time install of units
bash /home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/deploy/install-all.sh
```

## C) Trading-core MCP tools (if that server is connected)

| Tool | Purpose |
|------|--------|
| `mcp_diagnostics` | API up?, Telegram/Alpaca flags, recent MCP failures + `request_id` |
| `api_health` | GET :8080/health |
| `dashboard_url` | Local + Tailscale dashboard links (`tailscale_error` if Tailscale fails) |
| `telegram_debug` | Config check + test send |
| `telegram_test` | Send test message |
| `research_scan_mcp` | Propose-only scan + notify |
| `risk_pause` / `risk_resume` | Kill switch |

Dashboard “refresh” is automatic via WebSocket (`/ws/live`). Opening the URL is done on your phone; MCP returns the URL via `dashboard_url`.

## D) Diagnosing MCP failures

**Trading-core MCP** (this repo, `python -m src.mcp.server`):

1. Call `mcp_diagnostics` — shows API reachability, Telegram/Alpaca flags, last failures + `request_id`.
2. Match `request_id` in `python/data/reports/mcp.log`.
3. Tool JSON on failure includes `error_type`, `hint`, and `log_file` (not a bare `{"error": "..."}`).

**Fleet Pi MCP** (live process under `~/pi-tools/fleet/`):

- Allowlist denials return `blocked: …` (no command is run).
- Audit trail: `~/pi-tools/fleet/audit.jsonl` (do not commit).
- HTTP `fetch failed` / MCP `-32001` timeout is the Cursor↔Pi transport (Tailscale / `pi-mcp.service`), not a trading-core tool bug. Check `systemctl --user status pi-mcp.service`.

**Pi3 worker** (`host="pi3"`, Tailscale `100.85.88.91`):

- Pi3 is SSH-only. There is no second FastMCP. Use fleet tools with `host="pi3"`.
- `cpu_temp` / `system_summary` should return `26.1 C`, not `temp=temp=26.1'C`.
- SSH timeouts log on the **primary** (`~/pi-tools/fleet/mcp.log`) with a Tailscale / `id_ed25519_fleet` hint.
- `list_ai_clis` on Pi3 is `present=no` by design (see pi-remote `docs/PI3.md`).
- `run_command` cannot chain (`hostname; uname`); use `system_summary` or `host_diagnostics`.
- After pulling pi-remote: `python3 scripts/18-patch-live-fleet-pi3.py` then restart `pi-mcp.service` so the live 35k server keeps extra tools.

