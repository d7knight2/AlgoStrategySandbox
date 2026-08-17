# Lumibot Strategy Templates

This folder contains strategy templates for running with Lumibot + Alpaca paper trading.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set environment variables:

```bash
export APCA_API_KEY_ID=your_key
export APCA_API_SECRET_KEY=your_secret
export APCA_API_BASE_URL=https://paper-api.alpaca.markets
```

## Strategies

| Catalog ID | File | Description |
|------------|------|-------------|
| `opening-range-breakout` | `orb_strategy.py` | Intraday ORB with volume filter and stop management |
| `sma-regime-rotation` | `sma_regime_rotation.py` | Daily SPY regime rotation with allocation caps |
| `mean-reversion-rsi` | `mean_reversion_rsi.py` | RSI(2) oversold basket with ATR stops and take-profits |

Shared utilities live in `indicators.py` and `risk.py`. Strategy lookup is in `registry.py`.

## Run

Backtest (Yahoo data):

```bash
python run_backtest.py opening-range-breakout --start 2023-01-01 --end 2024-01-01
python run_backtest.py sma-regime-rotation
python run_backtest.py mean-reversion-rsi
```

Paper trading (requires Alpaca paper credentials):

```bash
python run_paper.py opening-range-breakout
```

## Tests

```bash
pip install pytest pandas
pytest test_indicators.py test_risk.py -q
```

> These are educational templates and should be paper-tested before any live usage.

## Cursor MCP

Project MCP config lives in `.cursor/mcp.json`:

- **pi** — edit and run strategy code in `strategies/lumibot/`
- **alpaca** — check account, positions, orders, and market data via Alpaca paper API

Set `PI_MCP_API_KEY`, `ALPACA_API_KEY`, and `ALPACA_SECRET_KEY` in Cursor before using either server.
