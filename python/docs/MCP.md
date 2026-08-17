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
- `get_health`
- `get_account`
- `get_positions`
- `get_orders`
- `get_market_status`
- `get_quote(symbol)`
- `get_bars(symbol, limit?)`
- `get_signals(symbol)`
- `get_risk_status`
- `run_backtest(symbol, limit?, initial_cash?)`

### Proposal / control
- `propose_trade(symbol, side, notional?, qty?, strategy_version?)`
- `risk_pause`
- `risk_resume`

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
