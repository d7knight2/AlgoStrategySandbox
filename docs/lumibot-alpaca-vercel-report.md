# Lumibot + Alpaca Research and Integration Report

## Objective

Integrate strategy research into AlgoStrategySandbox, build paper-trading-ready strategy templates, and define a deployment model that uses Vercel for the web control plane.

## Key Findings

1. Lumibot supports strategy development and broker adapters suitable for Alpaca execution.
2. Alpaca provides dedicated paper trading endpoints and keys for safe strategy validation.
3. Vercel is excellent for dashboards, APIs, and scheduled triggers, but a long-running stateful trading engine should run in a separate worker environment.

## Recommended Architecture

```text
User -> Vercel Next.js UI (/report, /portfolios)
      -> Vercel API route / cron trigger
      -> Worker service (Python + Lumibot)
      -> Alpaca Paper Trading API
```

### Why this architecture

- Keeps the trading runtime isolated from web request time limits.
- Enables clean separation between strategy execution and monitoring UI.
- Allows easy migration from paper to live by only switching credentials and risk gates.

## Strategy Prototypes Added

### 1) Opening Range Breakout (ORB)

- Symbol default: SPY
- Session signal: Break above opening range high
- Risk: position size based on stop-distance and fixed risk fraction
- File: `strategies/lumibot/orb_strategy.py`

### 2) SMA Regime Rotation

- Regime filter: SPY close relative to SMA(200)
- Risk-on basket: SPY, QQQ
- Risk-off basket: SHY, IEF
- File: `strategies/lumibot/sma_regime_rotation.py`

## Integration Plan Into This Repository

1. Research summaries and strategy catalog are exposed on `src/pages/report.tsx`.
2. Strategy metadata is centralized in `src/lib/research/lumibotAlpacaReport.ts`.
3. Python strategy templates are stored under `strategies/lumibot/`.
4. Home page links to the report for discoverability.

## Paper Trading Workflow

1. Configure paper credentials:
   - `APCA_API_KEY_ID`
   - `APCA_API_SECRET_KEY`
   - `APCA_API_BASE_URL=https://paper-api.alpaca.markets`
2. Backtest strategies and capture metrics.
3. Run for 2-4 weeks in paper mode.
4. Promote only if max drawdown, slippage, and fill quality stay within defined limits.

## Vercel Deployment Workflow

1. Deploy Next.js app to Vercel.
2. Add environment variables for dashboard + webhook settings.
3. Configure Vercel Cron to call a health-check or orchestration endpoint.
4. Host Lumibot worker in a Python container runtime (outside Vercel request path).
5. Surface worker health and strategy status back in the dashboard.

## Source References

- https://lumibot.lumiwealth.com/
- https://alpaca.markets/sdks/python/
- https://docs.alpaca.markets/docs/getting-started-with-paper-trading
- https://vercel.com/docs/cron-jobs
- https://vercel.com/docs/functions/runtimes/python
