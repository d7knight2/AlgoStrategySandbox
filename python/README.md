# Python Trading Core (Phase 1)

This directory contains the core trading system for the Raspberry Pi AI Trading System.

## Status

**Phase 1 only** — Paper trading foundation.

- Configuration system
- Alpaca PAPER broker abstraction (read-only)
- SQLite database skeleton
- Health-check endpoint
- Tests

**No order submission. No live trading path. Risk engine is stubbed.**

## Safety Rules

- `TRADING_MODE` is forced to `paper`
- API keys are loaded from `/etc/alpaca/env` (or local `.env`)
- AI cannot bypass risk controls (future phases)
- Live trading requires explicit, multi-step confirmation

## Quick Start

```bash
cd python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy example env (never commit real secrets)
cp .env.example .env

# Run health check
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Then visit: http://localhost:8000/health

## Directory Layout

```
python/
├── src/
│   ├── broker/          # Alpaca abstraction
│   ├── config/          # Settings & secrets loading
│   ├── database/        # SQLite models & session
│   ├── risk/            # Stub for Phase 1
│   └── main.py          # FastAPI entrypoint
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```
