# Paper copy-trade of public disclosures

Daily Telegram digest of **public, delayed** STOCK Act filings (House/Senate) plus
famous-investor 13F metadata. Optional **Alpaca paper** copies go through
`RiskEngine` with a small notional cap. Live trading stays disabled.

This is **not** financial advice and **not** a way to match politicians' dollar
size. Disclosures are often ~45 days late. We copy *direction* (buy/sell) at
`COPYTRADE_MAX_NOTIONAL` (default $100).

## What it uses

| Feed | Source | Notes |
|------|--------|--------|
| House / Senate STOCK Act | GitHub mirrors of official PTR filings (S3 stock-watcher buckets now 403) | Tickers like `N/A`, options, and `--` are skipped |
| Famous-investor 13F | SEC `data.sec.gov` submissions (Berkshire, Pershing Square, Icahn) | Filing date + EDGAR link only. User-Agent must be `Name email@domain` — GitHub noreply addresses get 403. |
| Sentiment | alternative.me Fear & Greed (no API key) | Crypto-heavy public gauge |
| Reddit | Public `reddit.com/search.json` (no OAuth) | 7-day ticker + filer chatter; 403s from some IPs |
| Price stats | Alpaca IEX daily bars | Trailing 7d/30d, volume, and 7d/30d *after* the disclosed buy |
| Leverage | Catalog + name heuristics | Flags 2x/3x and inverse ETFs (TQQQ, SOXL, NVDL, …) |

Default politician watchlist (`COPYTRADE_FILERS`):

Nancy Pelosi, Paul Pelosi, Tommy Tuberville, Josh Gottheimer, Michael McCaul, Dan Newhouse, Ro Khanna

Override in `/etc/alpaca/env` or `python/.env`:

```bash
COPYTRADE_FILERS=Nancy Pelosi,Paul Pelosi,Warren Buffett
COPYTRADE_LOOKBACK_DAYS=45
COPYTRADE_MAX_NOTIONAL=100
# Settings default is false. The systemd timer passes --execute for paper fills.
COPYTRADE_EXECUTE_PAPER=false
```

## Daily job

Weekdays **17:00** local Pi time (`trading-copytrade.timer`), after the 16:05
progress report.

- Telegram HTML digest: new watchlist filings, **ticker research** (Reddit 7d
  sentiment, trailing 7d/30d, post-buy 7d/30d, leveraged-product flag), paper
  copies, overlap between **your paper positions** and **shadow holdings** of
  tracked filers, 13F dates, Fear & Greed.
- `--execute` on the timer submits Alpaca **paper** market orders only after
  `RiskEngine` ALLOW. Duplicate disclosures are stored in `copytrade_seen`.
- Shadow book (`shadow_holdings`) tracks last known public direction per filer
  and symbol so the digest can say “your paper NVDA vs Pelosi BUY”.

Digest-only (no orders):

```bash
cd python
PYTHONPATH=. python -m src.copytrade.daily --no-notify
# or with Telegram, still no fills:
PYTHONPATH=. python -m src.copytrade.daily
```

Paper fills (still not live):

```bash
PYTHONPATH=. python -m src.copytrade.daily --execute --max-notional 100
```

## HTTP

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/copytrade/watchlist` | Filers + caps |
| GET | `/copytrade/latest` | Last `data/reports/copytrade_latest.json` |
| POST | `/copytrade/run` | Run now (`execute`, `notify`, `lookback_days`, `max_notional` query params) |

```bash
curl -s http://127.0.0.1:8080/copytrade/watchlist
curl -s -X POST 'http://127.0.0.1:8080/copytrade/run?notify=true&execute=false'
```

## MCP

Trading-core tool `copytrade_daily` hits the API, or runs in-process if :8080 is down.
Default `execute=false`. Fleet allowlist patterns are in `python/docs/MCP_OPS.md`.

## Safety

- `TRADING_MODE=paper` is still forced.
- Every copy goes through `RiskEngine` (`max_order_dollars` = the copy cap).
- Kill switch (`POST /risk/pause`) still blocks new orders.
- No Telegram inbound buy/sell commands.
- Do not treat delayed public filings as a live signal.

Agent playbook and free-API catalog: `.cursor/skills/gov-official-disclosures/SKILL.md`.
