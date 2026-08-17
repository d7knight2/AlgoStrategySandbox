# MCP Integration (Phase 9 foundation)

## Purpose

Expose the trading core to AI agents via the Model Context Protocol **without** giving them unrestricted trading power.

| Tool type        | Available now | Notes |
|------------------|---------------|-------|
| Read-only        | ✅            | account, positions, quotes, signals, risk, backtest |
| Propose trade    | ✅            | Always passes through RiskEngine; recorded only |
| Execute / submit | ❌            | Deliberately not registered |

## Tools exposed

### Read-only
- `get_health` — local process flags (works if the HTTP API is down)
- `api_health` — `GET :8080/health` on the running dashboard API
- `mcp_diagnostics` — API reachability, config flags, recent tool failures
- `get_account`
- `get_positions`
- `get_orders(status?)`
- `get_market_status`
- `get_quote(symbol)`
- `get_bars(symbol, limit?)`
- `get_signals(symbol)`
- `get_risk_status` — prefers the API so kill-switch state is shared
- `run_backtest(symbol, limit?, initial_cash?)`
- `dashboard_url` — local + Tailscale links; includes `tailscale_error` if `tailscale ip` fails

### Proposal / control
- `propose_trade(symbol, side, notional?, execute?)`
- `copytrade_daily(execute?, notify?, lookback_days?, max_notional?)` — public STOCK Act / 13F digest with Reddit 7d sentiment, 7d/30d stats, and leveraged-ETF flags; paper fills only if `execute=true`
- `risk_pause` / `risk_resume` — API first, local fallback with `api_error` + `hint`
- `research_scan_mcp` — propose-only scan via API first
- `telegram_debug` / `telegram_test`

## Failure logging

Every tool goes through `safe_tool` in `src/mcp/tooling.py`.

- **stderr** (INFO): `START` / `OK` / `FAIL` lines with `tool=` and `request_id=`
- **file** (DEBUG + traceback): `python/data/reports/mcp.log` (gitignored)
- On failure the JSON payload includes `ok: false`, `tool`, `request_id`, `error_type`, `error`, `hint`, `log_file`
- HTTP API calls log method + path + status. They never log Telegram bot tokens (token is in the URL path; we log the path only as `/alerts/...` on the local API)
- `mcp_diagnostics` returns the last 20 failures from the current MCP process

When a tool looks “empty” or generic, call `mcp_diagnostics` first, then grep the log:

```bash
tail -n 80 /home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/data/reports/mcp.log
```

## How to run

```bash
cd python
source .venv/bin/activate   # if using venv
pip install -r requirements.txt

# stdio transport (typical for Cursor / Claude Desktop / local agents)
python -m src.mcp.server
```

Example client config (Cursor / Claude Desktop style):

```json
{
  "mcpServers": {
    "trading-core": {
      "command": "/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python/.venv/bin/python",
      "args": ["-m", "src.mcp.server"],
      "cwd": "/home/d7knight/repos/d7knight2/AlgoStrategySandbox/python",
      "env": {}
    }
  }
}
```

Credentials are still loaded from `/etc/alpaca/env` (or process environment). Never put keys in the MCP config.

## Relationship to official Alpaca MCP

Alpaca provides an official MCP server that can place orders directly.  
**We do not use that for execution.** Our MCP layer sits in front of our own RiskEngine so an AI cannot bypass hard limits, the kill switch, or paper-only mode.

You may still use Alpaca’s official MCP for pure market-data exploration if desired; all *trading decisions* in this project must go through `propose_trade`.

## Safety invariants

1. `TRADING_MODE=paper` is enforced by settings validation.
2. Alpaca client is constructed with `paper=True`.
3. Every proposal is evaluated by `RiskEngine` before being recorded.
4. No `submit_order` / `execute_trade` tool exists in this server.
5. Kill switch (`risk_pause`) immediately rejects new proposals.

## Next steps (require approval)

- Add a paper-only `execute_approved_proposal` tool that submits to Alpaca **only** after RiskEngine ALLOW and only while paper mode is active.
- Optional: HTTP/SSE transport for remote agents.
- Wire MCP tools into a scheduled research loop.
