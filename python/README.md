# Python Trading Core

Production-oriented paper-trading foundation for the Raspberry Pi AI Trading System.

## Current Status (v0.10.0)

Phases 1–7 foundation implemented:

| Area              | Status                                      |
|-------------------|---------------------------------------------|
| Config + secrets  | ✅ Forces `TRADING_MODE=paper`               |
| Alpaca PAPER API  | ✅ Read-only (account, positions, orders, clock) |
| Market data       | ✅ Quotes + historical bars                  |
| Signals           | ✅ SMA/EMA/RSI + deterministic scorer        |
| Risk engine       | ✅ Hard limits + kill switch (AI cannot bypass) |
| Paper proposals   | ✅ Propose → Risk → Audit record |
| Paper orders      | ✅ Explicitly gated paper submission       |
| Backtest skeleton | ✅ Chronological, no look-ahead              |
| SQLite audit      | ✅ Signals, proposals, fills, snapshots      |
| FastAPI           | ✅ Health + all read/propose endpoints       |

**Still disabled by design**
- Real order submission
- Live trading path
- AI unrestricted execution

## Safety Rules (enforced in code)

- `TRADING_MODE` must be `"paper"` (validator rejects anything else)
- Alpaca client always created with `paper=True`
- Every proposed trade passes through `RiskEngine.evaluate()`
- Kill switch: `POST /risk/pause`
- No live capital path exists yet
- Paper automation is opt-in via `PAPER_AUTOMATION_ENABLED=true`

## Quick Start

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Credentials are loaded from /etc/alpaca/env on the Pi
uvicorn src.main:app --host 0.0.0.0 --port 8080
```

Open http://localhost:8080/docs for interactive API.

## Key Endpoints

| Method | Path                    | Purpose                          |
|--------|-------------------------|----------------------------------|
| GET    | `/health`               | Safety flags                     |
| GET    | `/account`              | Paper account                    |
| GET    | `/positions`            | Open positions                   |
| GET    | `/signals/{symbol}`     | Indicators + score               |
| POST   | `/propose_trade`        | Risk-validated proposal (no fill)|
| GET    | `/backtest/{symbol}`    | Simple chronological backtest    |
| GET    | `/copytrade/watchlist`  | Public-filer watchlist + caps    |
| POST   | `/copytrade/run`        | STOCK Act / 13F digest (paper)   |
| GET    | `/risk/status`          | Current limits                   |
| POST   | `/risk/pause`           | Emergency kill switch            |

## Tests

```bash
pytest -v
```

## Next Phases (require explicit approval)

- Scheduled paper order submission after setting `PAPER_AUTOMATION_ENABLED=true`
- Scheduled paper trading loop
- MCP server tools
- Dashboard / monitoring
- AI analysis layer (structured JSON only)
- Live trading (multi-step confirmation + tiny capital only)

Never represents backtests as proof of future profitability.
