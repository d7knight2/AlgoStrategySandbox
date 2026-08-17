# Free public APIs and bulk files for official-trade data

Companion to the `gov-official-disclosures` skill. **No API key** unless noted. Prefer these over paid aggregators.

Last verified in-repo: House/Senate GitHub JSON mirrors and alternative.me Fear & Greed work from the Pi. SEC `data.sec.gov` often **403**s from cloud/Pi IPs even with a User-Agent.

## 1. Congressional STOCK Act (politician brokerage disclosures)

Official sites have **no supported public REST API** for a clean trade tape. Use official bulk files or community JSON that republishes the same PTRs.

### Official (free, no key)

| Source | URL / pattern | Notes |
|--------|----------------|-------|
| House Clerk search/download | https://disclosures-clerk.house.gov/FinancialDisclosure | Human UI |
| House yearly FD ZIP | `https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{YYYY}FD.zip` | Confirmed HTTP 200 for 2024–2026; mostly PDFs/index, not a tick tape |
| House PTR PDF | `https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{YYYY}/{filingId}.pdf` | One filing per PDF |
| Senate eFD search | https://efdsearch.senate.gov/search/home/ | Must accept terms in a browser session. **Not** a documented bulk API. Do not automate the gate. |

### Community JSON (free, no key) — what this repo uses

S3 `house-stock-watcher-data` / `senate-stock-watcher-data` buckets now return **403**. Use GitHub (and jsDelivr) first.

| Chamber | URLs (first 200 wins in `python/src/feeds/congress.py`) |
|---------|---------------------------------------------------------|
| Senate | `https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json` |
| Senate CDN | `https://cdn.jsdelivr.net/gh/timothycarambat/senate-stock-watcher-data@master/aggregate/all_transactions.json` |
| House | `https://raw.githubusercontent.com/TattooedHead/house-stock-watcher-data/main/data/all_transactions.json` |
| House CDN | `https://cdn.jsdelivr.net/gh/TattooedHead/house-stock-watcher-data@main/data/all_transactions.json` |

Typical row fields: `representative` or `senator`, `ticker`, `type` (`Purchase`/`Sale`), `amount` (range), `disclosure_date`, `transaction_date`, `asset_description`, `asset_type`.

Treat mirrors as **unofficial caches** of official PTRs. If they go stale, fall back to House ZIP/PDFs — not to paid scrapers.

### Paid / key (do not add unless the user asks)

Quiver Quant congress endpoint, Unusual Whales Congress, Financial Modeling Prep senate/house trading, Capitol Trades commercial BFF, Apify congress actors.

## 2. SEC EDGAR (managers + corporate insiders) — official, free, no key

Docs: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data  
Developer: https://www.sec.gov/about/developer-resources

**Required headers** (or you get 403 "Undeclared Automated Tool"):

```
User-Agent: AlgoStrategySandbox paper-research@example.com
Accept-Encoding: gzip, deflate
```

GitHub `users.noreply.github.com` addresses are treated as undeclared and 403. This repo’s client is in `python/src/feeds/http.py`.

Rate limit: **10 requests/second**. Sleep ~200ms between 13F CIKs.

| Endpoint | Use |
|----------|-----|
| `GET https://data.sec.gov/submissions/CIK{10-digit}.json` | Filing history. This repo uses it for latest **13F** date + accession |
| `GET https://data.sec.gov/api/xbrl/companyfacts/CIK{10-digit}.json` | Fundamentals (not trades) |
| `GET https://www.sec.gov/files/company_tickers.json` | Ticker ↔ CIK |
| Archives | `https://www.sec.gov/Archives/edgar/data/{cikNoPad}/{accessionNoDash}/` |
| Daily/full indexes | `https://www.sec.gov/Archives/edgar/daily-index/` and `.../full-index/` |
| Form 4 ownership XML | Inside the accession dir (`*.xml`) — **company** insiders, not Congress |
| 13F information table | XML/HTML inside the 13F accession — full holdings; this repo does **not** dump it into $100 copies |

Default 13F CIKs in `python/src/feeds/sec13f.py`: Berkshire `0001067983`, Pershing Square `0001336528`, Icahn Enterprises `0000812011`.

If submissions JSON 403s from the Pi, report unavailable. Do not loop retries.

## 3. Related official APIs (not personal stock copies)

| API | Key | What it is |
|-----|-----|------------|
| https://api.congress.gov | Free key from api.data.gov | Bills, members, votes — **not** PTRs |
| https://api.open.fec.gov/v1/ | Free FEC key | Campaign receipts/disbursements — **not** brokerage trades |
| https://unitedstates.github.io/congress-legislators/legislators-current.json | None | Names, bioguide IDs, terms — join keys for PTRs |

## 4. Sentiment (context only)

| API | Key | Notes |
|-----|-----|--------|
| `https://api.alternative.me/fng/?limit=1&format=json` | None | Crypto-heavy Fear & Greed; wired in `python/src/feeds/sentiment.py` |
| `https://www.reddit.com/search.json?q=NVDA&sort=hot&t=week&limit=25` | None | Public JSON search. Needs a descriptive User-Agent. Datacenter IPs often **403**. Wired in `python/src/feeds/reddit.py`. Score titles with a small bull/bear lexicon; count posts that mention Pelosi/Congress/PTR. |

Do not size paper copies from these gauges. They are digest context.

## 4b. Price stats and leveraged products

| Input | What the digest shows |
|-------|------------------------|
| Alpaca IEX daily bars (`AlpacaMarketData.get_bars`) | Trailing **7d** and **30d** return, 7d vs 30d volume. If the PTR `transaction_date` is old enough: return **7d after buy**, **30d after buy**, and since the event. |
| `python/src/feeds/leverage.py` | Catalog of common 2x/3x/inverse ETFs plus name heuristics (`3X`, `UltraPro`, `Direxion Daily`). YieldMax-style covered-call funds are flagged as option-income, not leveraged. |

Paper copies of leveraged names still use the $100 cap. The digest warns; it does not skip them.

## 5. HTTP client rules in this repo

`python/src/feeds/http.py` sends a descriptive User-Agent and JSON Accept. Keep Telegram `httpx` loggers at WARNING so bot tokens in `/bot<token>/sendMessage` never hit INFO logs.

## 6. How acting works (paper)

1. Fetch watchlist PTRs (`fetch_watchlist_trades`).
2. Skip seen `event_key`.
3. Upsert `shadow_holdings`.
4. `propose_and_validate` or `execute_approved` with notional = `COPYTRADE_MAX_NOTIONAL`.
5. Research unique tickers: leverage flag, trailing 7d/30d, post-buy 7d/30d, Reddit 7d.
6. Telegram HTML digest; overlap paper positions vs shadow book.
7. Weekday systemd: `python/deploy/trading-copytrade.timer`.

Never wire Telegram inbound buy/sell. Never set `TRADING_MODE=live`.
