export interface StrategyCard {
  id: string;
  name: string;
  market: string;
  timeframe: string;
  riskRules: string[];
  summary: string;
  lumibotSketch: string;
}

export interface IntegrationStep {
  title: string;
  details: string;
}

export interface DeploymentNote {
  title: string;
  details: string;
}

export const strategyCards: StrategyCard[] = [
  {
    id: 'opening-range-breakout',
    name: 'Opening Range Breakout (ORB)',
    market: 'US Equities',
    timeframe: '5-min candles, day trading window',
    riskRules: [
      'Max 1% account risk per trade',
      'Stop loss below range low for longs / above range high for shorts',
      'No new entries after 14:30 ET',
    ],
    summary:
      'Capture intraday momentum once price breaks the first 15-30 minute range with volume confirmation.',
    lumibotSketch:
      'At market open build opening range; if breakout + volume filter pass then submit bracket order via Alpaca paper account.',
  },
  {
    id: 'sma-regime-rotation',
    name: 'SMA Regime Rotation',
    market: 'SPY + defensive ETF basket',
    timeframe: 'Daily bars',
    riskRules: [
      'Risk-off if SPY closes below 200-day SMA',
      'Monthly rebalance frequency',
      'Max 30% allocation per non-cash asset',
    ],
    summary:
      'Use trend regime detection to rotate between risk-on and defensive ETFs while preserving capital in downtrends.',
    lumibotSketch:
      'If SPY close > SMA200 allocate to SPY/QQQ split; otherwise rotate to SHY/IEF and rebalance monthly.',
  },
  {
    id: 'mean-reversion-rsi',
    name: 'RSI Mean Reversion Basket',
    market: 'Liquid large-cap equities',
    timeframe: 'Daily scan with intraday execution',
    riskRules: [
      'Only trade symbols with average volume > 2M',
      'Hard stop at 2 ATR',
      'Take-profit ladder at +1 ATR and +2 ATR',
    ],
    summary:
      'Buy oversold names in an uptrend and scale out as price mean-reverts.',
    lumibotSketch:
      'Nightly scan for RSI(2) < 10 and close > SMA50; queue bracket orders for next session open on Alpaca paper endpoint.',
  },
];

export const integrationSteps: IntegrationStep[] = [
  {
    title: '1) Local Python strategy workspace',
    details:
      'Create a /strategies/lumibot folder with reusable indicators, risk utilities, and strategy classes. Keep broker credentials in .env and never in repo.',
  },
  {
    title: '2) Alpaca paper trading credentials',
    details:
      'Use APCA_API_BASE_URL=https://paper-api.alpaca.markets and dedicated paper keys to validate order routing and position sync.',
  },
  {
    title: '3) Backtest to paper promotion gates',
    details:
      'Define objective gates (Sharpe, max drawdown, win-rate stability) before enabling a strategy in paper mode. Persist all metrics in this app for review.',
  },
  {
    title: '4) Vercel deployment split',
    details:
      'Deploy this Next.js dashboard on Vercel for monitoring/configuration. Run Lumibot execution workers on a Python-capable worker host; trigger health checks from Vercel Cron/API routes.',
  },
];

export const deploymentNotes: DeploymentNote[] = [
  {
    title: 'Why split services?',
    details:
      'Trading engines are stateful and often long-running, while Vercel functions are request/response and time-bounded. Split improves reliability and restart control.',
  },
  {
    title: 'Recommended deployment path',
    details:
      'Vercel hosts UI + API proxy. Worker host (e.g., container VM) runs Lumibot and connects to Alpaca paper/live APIs. Use webhook or queue to pass strategy changes.',
  },
  {
    title: 'Operational checklist',
    details:
      'Add structured logs, per-strategy kill-switch, drawdown circuit-breakers, and heartbeat alerts before moving from paper to live.',
  },
];

export const researchSources: string[] = [
  'https://lumibot.lumiwealth.com/ (Lumibot docs)',
  'https://alpaca.markets/sdks/python/ (Alpaca Python SDK docs)',
  'https://docs.alpaca.markets/docs/getting-started-with-paper-trading (Alpaca paper trading docs)',
  'https://vercel.com/docs/cron-jobs (Vercel cron docs)',
  'https://vercel.com/docs/functions/runtimes/python (Vercel Python runtime docs)',
];
