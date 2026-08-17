---
name: gov-official-disclosures
description: Follow public U.S. government-official and politician stock disclosures (STOCK Act, House/Senate PTRs, SEC 13F) and act on them only through this repo's paper, risk-gated copy-trade path. Use when the user asks about politician trades, congressional insider filings, copying Pelosi/Buffett, free public APIs for government trades, or daily Telegram alerts for those feeds.
---

# Government-official disclosure data (paper only)

Use this skill when the user wants to **follow** public filings by members of Congress, political insiders, or famous investment managers, and optionally **act** on them in AlgoStrategySandbox.

This is **public, delayed disclosure data**, not non-public insider information. It is **not** financial advice. In this repo, acting means **Alpaca paper** after `RiskEngine` ALLOW. Never enable live trading.

## What the data actually is

| Dataset | Who | Typical delay | What you get |
|---------|-----|---------------|--------------|
| STOCK Act Periodic Transaction Reports (PTRs) | U.S. House and Senate members (and some staff/candidates) | Often up to **45 days** after the trade | Ticker (messy), buy/sell, **amount range** not exact dollars |
| SEC Form 13F | Institutional managers (Buffett/Berkshire, Ackman, Icahn, …) | ~**45 days after quarter end** | Holdings snapshot, not a live order stream |
| SEC Forms 3/4/5 | Corporate officers and 10% owners | Form 4 often **2 business days** | Company-insider trades — **not** members of Congress |
| FEC / OpenFEC | Campaign committees | Hours to days | **Donations**, not personal brokerage trades |
| Congress.gov | Members' legislative activity | Near real time | Bills and votes — **not** stock trades |

Do not treat a PTR as a live signal. Copy **direction** (buy/sell) at a small notional cap. Do not copy the disclosed dollar range.

## Follow vs act (this repo)

**Follow** = ingest public JSON, dedupe, Telegram digest, shadow book of last known direction.

**Act** = `PaperExecutionEngine` after `RiskEngine`. Caps: `COPYTRADE_MAX_NOTIONAL` (default $100), `max_trades_per_day` (10), no shorting, no options, `TRADING_MODE=paper`.

Default politician watchlist (`COPYTRADE_FILERS`): Nancy Pelosi, Paul Pelosi, Tommy Tuberville, Josh Gottheimer, Michael McCaul, Dan Newhouse, Ro Khanna.

### Run it

```bash
cd python
PYTHONPATH=. python -m src.copytrade.daily --no-notify          # digest only
PYTHONPATH=. python -m src.copytrade.daily                      # Telegram, no fills
PYTHONPATH=. python -m src.copytrade.daily --execute            # Alpaca PAPER after ALLOW
```

HTTP (Pi trading-api `:8080`): `GET /copytrade/watchlist`, `GET /copytrade/latest`, `POST /copytrade/run`.

MCP: `copytrade_daily` (default `execute=false`). Weekday timer `trading-copytrade.timer` at 17:00 PT uses `--execute`.

Code: `python/src/feeds/congress.py`, `python/src/feeds/sec13f.py`, `python/src/feeds/sentiment.py`, `python/src/copytrade/engine.py`. Operator notes: `python/docs/COPYTRADE.md`. API catalog: [references/public-apis.md](references/public-apis.md).

## Agent rules

1. Prefer **already-wired feeds** in `python/src/feeds/`. Do not add paid APIs (Quiver, Unusual Whales, FMP congress, Capitol Trades commercial) unless the user supplies a key and asks.
2. Prefer **published JSON or official bulk files**. Do not automate the Senate eFD terms-of-use checkbox, CSRF, or Akamai bypass.
3. Skip junk tickers: `N/A`, `--`, options, preferred shares, multi-word descriptions. See `normalize_ticker` / preferred skip in `congress.py`.
4. Dedupe with `CopyTradeSeen.event_key`. Do not replay a 45-day backfill into paper orders if those keys are already stored.
5. Sells without a long paper position **REJECT** (shorting disabled). That is correct.
6. SEC requests need `User-Agent: AppName contact@email.com`, `Accept-Encoding: gzip, deflate`, ≤10 req/s. A 403 "Undeclared Automated Tool" means the IP/UA was blocked — surface it in the digest, do not hammer retries.
7. Never log Telegram bot tokens (they sit in the request URL). Keep `httpx` at WARNING around sends.
8. If asked for live capital, real-money copy-trading, or using non-public information: refuse. Paper path only.

## When a feed is empty or 403

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| House/Senate S3 `403` | Old stock-watcher buckets are closed | Use GitHub mirrors listed in `congress.py` |
| SEC `data.sec.gov` `403` | Missing/weak User-Agent or datacenter IP | Keep UA with email; show "unavailable" in digest |
| Watchlist empty on 7-day lookback | STOCK Act delay | Default lookback is **45 days** |
| Preferred tickers (`GOOGM`) | PTR lists convertibles | Skip; not common stock |
| 13F "no trades today" | Quarterly, not daily | Report latest **filing date + EDGAR link** only |

## Adding a filer or a free source

1. Filers: set `COPYTRADE_FILERS` in `/etc/alpaca/env` or `python/.env` (comma-separated name substrings).
2. New 13F manager: add `{name, cik, manager}` in `python/src/feeds/sec13f.py` `DEFAULT_MANAGERS`.
3. New free JSON URL: append to `SENATE_URLS` / `HOUSE_URLS` (first success wins). Add a test that does **not** hit the network (mock `get_json`).
4. Do not scrape HTML search forms. Official House bulk ZIP/PDFs are allowed if JSON mirrors die; parse offline, don't DDoS the Clerk.

## Safety invariants

- Public delayed filings only.
- Paper only; RiskEngine in front of every order.
- Copy direction, not size.
- Telegram is outbound alerts, not a trade command channel.
- Not advice; not a claim that delayed PTRs beat the market.
