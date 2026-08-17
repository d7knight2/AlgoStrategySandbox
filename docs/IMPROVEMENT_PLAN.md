# Telegram + Algo Strategy Improvement Plan

> Status note: this document contains historical implementation notes. The
> current staged promotion plan is [AUTOPILOT_PLAN.md](AUTOPILOT_PLAN.md).
> Fleet allowlisting and Pi3 reachability work has since been applied; verify
> the live policy through Pi MCP before changing it.

Grounded in a live Pi MCP inspection of `RaspberryPi464bitOs` on 2026-08-16 (AlgoStrategySandbox `main` at `634dc5f`, trading-core **v0.8.0**).

This is a sequencing plan, not a claim that live trading is ready. Paper-only and RiskEngine remain hard constraints.

## Live baseline (Pi MCP)

| Check | Result |
|-------|--------|
| Primary Pi | Online, aarch64, load ~0.3, 32°C |
| Pi3 worker | **Offline** (`100.85.88.91` SSH timeout) |
| Trading API | `trading-api.service` active on `:8080` since 01:05 PDT |
| `/health` | `trading_mode=paper`, `telegram_configured=true`, `trading_paused=false` |
| Telegram test | `POST /alerts/telegram/test` → `{sent: true, message_id: 5}` |
| Research timer | Enabled; next fire **Mon 09:45 PDT** (propose-only) |
| Fleet MCP `policy.yml` | **Does not** include the trading curl / restart allowlist in `python/docs/MCP_OPS.md` |
| Separate Telegram repo | None — alerts live in this repo (`python/src/notifications/telegram.py`) |

Related open PRs (do not duplicate):

- [#6](https://github.com/d7knight2/AlgoStrategySandbox/pull/6) — Lumibot sandbox (ORB / SMA / RSI mean-reversion + runners). Draft.
- [#5](https://github.com/d7knight2/AlgoStrategySandbox/pull/5) — QuantConnect backtest list/run client helpers.

Companion repo `pi-remote` owns fleet MCP (`policy.yml`, `repos.yml`). Trading-core MCP is a **second** server in this repo (`python -m src.mcp.server`).

---

## Goals

1. **Telegram becomes a two-way ops remote** (status / pause / scan) without becoming an order-entry surface.
2. **Alerts become useful** (ALLOW / fills / kill switch), not a weekday spam of HOLD scans.
3. **The research scorer and risk gate tell the same story** — one kill switch, real daily-loss, market-hours awareness.
4. **Strategy work has a promotion path**: Lumibot research → Pi paper loop → dashboard/Telegram, without bypassing RiskEngine.
5. **Fleet MCP can operate the stack** (health, telegram test, scan, pause) after an explicit `pi-remote` allowlist change.

Non-goals until later human approval: live capital, inbound Telegram “buy SPY”, exposing bot tokens, or merging QuantConnect and Alpaca execution into one broker.

---

## Architecture (current vs target)

```text
TODAY
  systemd timers ──► research.loop (own RiskEngine) ──► Telegram sendMessage
  trading-api     ──► another RiskEngine (in-memory pause)
  trading-core MCP ──► third RiskEngine + HTTP to :8080
  fleet MCP       ──► deny-by-default shell (trading curls not allowlisted)
  Lumibot templates ──► not wired to Pi loop
  Next.js UI      ──► QuantConnect, not the Pi API

TARGET
  Telegram poller ──► trading-api only (auth: TELEGRAM_CHAT_ID)
  All scans/exec  ──► HTTP to :8080 so pause/daily-loss is shared
  Alerts          ──► severity + cooldown + market-hours
  Lumibot         ──► research worker; promotions emit propose_trade to API
  fleet MCP       ──► allowlisted localhost curls + systemctl status/restart
```

---

## Workstream A — Telegram (this repo)

### A0. Fix what is already live (small, do first)

| Item | Why | Where |
|------|-----|--------|
| HTML “escape” is a no-op | `replace("&", "&")` etc. in `generate_progress_report` can break Telegram HTML parse_mode | `python/src/reporting/progress.py` |
| Alert on every scan | Weekday 09:45 / 12:30 / 15:45 will ping even with zero ALLOW | `python/src/research/loop.py`, `format_scan_alert` |
| Tests only cover formatting | `send_telegram` has no mocked httpx tests; no retry/timeout cases | `python/tests/test_telegram.py` |
| Version drift | API `0.8.0` vs dashboard snapshot `0.7.0` | `python/src/main.py`, `python/src/monitoring/live.py` |

**Alert policy (proposed):**

- Always: kill switch, ALLOW proposal, paper fill, API down / credential failure.
- Daily: one progress report (already on `trading-report.timer`).
- Optional / quiet: HOLD-only scans — skip Telegram, still write SQLite.
- Never: secrets, raw tokens, execute-from-chat.

### A1. Inbound command bot (ops remote)

Keep **long-polling** (`getUpdates`) on the Pi. The box is on Tailscale; a public Telegram webhook is extra attack surface.

New module: `python/src/notifications/telegram_bot.py` + user unit `trading-telegram.service`.

| Command | Behavior | Safety |
|---------|----------|--------|
| `/start` `/help` | List commands | Chat-id allowlist |
| `/status` `/health` | Equity, pause, market, telegram flag | Read-only via API |
| `/positions` | Open paper positions | Read-only |
| `/pause` `/resume` | Kill switch | Same as dashboard; confirm with inline button |
| `/scan` | Propose-only universe scan | `execute=false` hardcoded |
| `/report` | Generate progress report | Notify once |

Hard rules:

- Ignore any chat id ≠ `TELEGRAM_CHAT_ID`.
- No `/buy`, `/sell`, `/execute`.
- Rate-limit (e.g. 1 scan / 60s).
- Offset persistence so the bot does not replay old commands after restart.

Wire: `POST /alerts/telegram/webhook` is **not** required for v1. Poller calls existing FastAPI routes.

Docs: extend `python/docs/TELEGRAM.md` (setup already good; add commands + “alerts are not execution”).

### A2. Message quality

- Shared formatter helpers: scan, ALLOW, fill, pause, daily report (HTML escaped once).
- Inline buttons on ALLOW: `Pause` / `Ignore` (pause only).
- Cooldown key: `(event_type, symbol)` so a stuck BUY does not triple-ping the same timer slot.
- Optional `TELEGRAM_QUIET_HOURS` (e.g. 21:00–07:00 PT).

### A3. Tests

- Mock `httpx` for send success/fail/timeout.
- Chat-id rejection for inbound.
- “HOLD-only scan does not send”.
- HTML escape of `<` in report text.

---

## Workstream B — Strategy + risk (this repo)

### B0. Correctness of the gate (before smarter signals)

These are bugs/gaps, not research ideas:

1. **Kill switch is process-local.** `RiskEngine.trading_paused` dies on API restart. Research timer and MCP each construct a **new** `RiskEngine()`, so dashboard STOP does not stop `python -m src.research.loop`.
   - Persist pause in SQLite (`SystemEvent` or a `risk_state` row) and have every loop/API/MCP **read it from the API** (`GET /risk/status`) rather than a private instance.
   - Practical rule: timers should `curl POST /research/scan` instead of importing `scan_universe` in a separate process.

2. **`max_daily_loss_percent` is unused.** `_daily_pnl` is never updated (`python/src/risk/engine.py`). Compute from account snapshots or Alpaca portfolio history and REJECT when breached.

3. **Research scans while the market is closed.** `scan_universe` still scores and may propose. Skip proposals (still snapshot account) unless `--force`.

4. **Paper fills store `price=0.0`.** Follow up with order get, or don’t pretend a fill exists until `filled_avg_price` is known (`python/src/execution/paper.py`).

5. **Dashboard WS writes an `AccountSnapshot` every ~5s** while a client is connected (`python/src/monitoring/live.py`). That inflates “equity Δ” in reports. Snapshot on a timer (e.g. 1–5 min) or only on trade/report.

6. **Stale docs:** `python/README.md` still says v0.3.0 and “no orders yet”; DASHBOARD.md still says port 8000.

### B1. Research scorer v2 (still deterministic)

Keep `research_v001` as the production default. Add `research_v002` behind a flag.

| Upgrade | Detail |
|---------|--------|
| Regime filter | Only BUY when SPY (or QQQ) is above SMA50/SMA200 — reuse the idea in `strategies/lumibot/sma_regime_rotation.py` |
| ATR / volatility sizing | Cap notional by ATR so NVDA and IWM are not the same $100 blindly |
| Position awareness | Don’t stack a second BUY if already long; SELL only to flatten |
| Tunable universe | Env `RESEARCH_UNIVERSE=SPY,QQQ,...` instead of hardcoded list |
| Confidence gate | Keep 0.4 for now; log near-misses (0.25–0.4) without proposing |
| Costs in backtest | Commission + spread bps; report max drawdown, Sharpe (with “illustrative only” note) |

Do **not** replace the scorer with an LLM. Optional later: LLM commentary *after* the deterministic decision, stored as text, never as the ALLOW bit.

### B2. Lumibot path (coordinate with PR #6)

PR #6 already adds mean-reversion RSI, ATR helpers, and `run_paper.py`. Plan after that lands (or rebase onto it):

1. Review #6 for RiskEngine bypass (Lumibot `submit_order` must not become a second live path on the Pi).
2. Run Lumibot **only** as a research worker: backtest + paper in its venv.
3. Promotion adapter: Lumibot signal → `POST /propose_trade` on `:8080` (RiskEngine + Telegram).
4. Do not run Lumibot and `research.loop` execute-paper on the same symbols without a lock.

QuantConnect (#5) stays the **cloud backtest** loop for the Next.js app. Pi remains Alpaca paper.

### B3. Next.js vs Pi

Low priority vs A/B0:

- `/report` already catalogs Lumibot; add a read-only “Pi health” card if a Tailscale URL + optional `TRADING_API_BASE` is set (server-side only).
- Do not put Alpaca/Telegram secrets in `NEXT_PUBLIC_*`.

---

## Workstream C — Pi fleet MCP (`pi-remote`, separate PR)

`python/docs/MCP_OPS.md` already lists the patterns. They are **not** in `pi-remote` `mcp/fleet/policy.yml` today (confirmed via `repo_read`).

Add allowlist (localhost only):

- `curl -s http://127.0.0.1:8080/health`
- `curl -s -X POST http://127.0.0.1:8080/alerts/telegram/test`
- `curl -s -X POST http://127.0.0.1:8080/research/scan`
- `curl -s -X POST http://127.0.0.1:8080/risk/(pause|resume)`
- `systemctl --user (status\|is-active\|restart) trading-api.service`
- `systemctl --user (status\|is-active\|list-timers) trading-.*`
- `tail -n N …/python/data/reports/(api\|cron\|research).log`

Then restart `pi-mcp.service`. Do **not** allowlist `--execute` or arbitrary curl to the public internet.

Optional: pin a LibreChat agent “Trading Core” that prefers `telegram_test` / `api_health` from trading-core MCP **or** these curls — not both in one confused prompt.

Pi3: restore Tailscale/SSH before treating it as a research worker. It is currently unreachable.

---

## Suggested implementation order

Do one vertical slice at a time; keep paper-only.

| Step | Scope | Done when |
|------|--------|-----------|
| 1 | A0 + B0.6 docs/version | HOLD scans quiet; report HTML valid; README matches v0.8 |
| 2 | B0.1–B0.3 shared risk via API | Dashboard pause stops the next timer scan |
| 3 | A1 inbound bot | `/status` and `/pause` work from the existing chat |
| 4 | B0.4–B0.5 fills + snapshot cadence | Report equity Δ is not WS noise |
| 5 | C fleet allowlist | This Cloud Agent can `curl` health/telegram/scan via Pi MCP |
| 6 | B1 scorer v2 | Backtest comparison table vs v001 on the same bars |
| 7 | B2 after #6 merge | Lumibot paper worker proposes through `:8080` |

---

## Safety invariants (do not regress)

- `TRADING_MODE` validator still rejects anything except `paper`.
- Alpaca client constructed with `paper=True`.
- No Telegram command submits orders.
- No MCP tool named like `submit_live_order`.
- Bot token never committed; fleet `secret_globs` already skip `.env` / `token`.
- Research timer stays propose-only until an explicit, documented change to `trading-research.service`.

---

## Verification (after each step)

On the Pi (via trading API or, after step 5, fleet MCP):

```bash
curl -s http://127.0.0.1:8080/health
curl -s -X POST http://127.0.0.1:8080/alerts/telegram/test
curl -s -X POST http://127.0.0.1:8080/risk/pause
# expect next /research/scan to REJECT / skip
curl -s -X POST http://127.0.0.1:8080/risk/resume
```

In-repo:

```bash
cd python && pytest -q
cd python && ruff check src tests
```

Telegram: one test message, one `/status`, no message on a HOLD-only scan.
