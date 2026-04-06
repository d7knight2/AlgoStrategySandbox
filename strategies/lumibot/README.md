# Lumibot Strategy Templates

This folder contains starter strategy templates for running with Lumibot + Alpaca paper trading.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install lumibot alpaca-py python-dotenv
```

Set environment variables:

```bash
export APCA_API_KEY_ID=your_key
export APCA_API_SECRET_KEY=your_secret
export APCA_API_BASE_URL=https://paper-api.alpaca.markets
```

## Templates

- `orb_strategy.py` - opening range breakout intraday template.
- `sma_regime_rotation.py` - daily trend regime rotation template.

> These are educational templates and should be paper-tested before any live usage.
