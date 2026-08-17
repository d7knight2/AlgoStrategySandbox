# Paper-first path to reliable automation

This is an engineering and validation plan, not a promise of profit. No
backtest, signal, or copy-trade result establishes that future returns will be
positive. The system must earn the right to automate one layer at a time.

## Current boundary

- The Python core is forced to `TRADING_MODE=paper`.
- `PAPER_AUTOMATION_ENABLED` defaults to `false`.
- AI and Telegram can research, report, pause, and resume; neither is an
  unrestricted order-entry surface.
- Every paper order must pass the deterministic `RiskEngine`.
- The Pi fleet remains deny-by-default and only exposes narrowly scoped
  commands.

## Promotion gates

Every strategy or automation change must pass these gates in order:

1. **Code gate** — CI is green: Ruff, unit tests, UI tests, and coverage.
2. **Data gate** — inputs are timestamped, deduplicated, and failures are
   visible; no silent fallback can create an order.
3. **Backtest gate** — use an untouched time period, include spread/fees and
   slippage assumptions, and report drawdown, turnover, exposure, and return
   distribution. Avoid selecting on one lucky period.
4. **Shadow gate** — run propose-only with no orders and compare expected versus
   observable fills, latency, missing data, and rejected actions.
5. **Paper gate** — enable paper automation only after explicit review. Keep a
   small notional cap, daily loss limit, trade-count limit, and kill switch.
6. **Reliability gate** — verify restart recovery, idempotency, stale-data
   handling, alert delivery, database backups, and recovery from a failed
   broker/feed request.
7. **Human promotion gate** — live trading is a separate change requiring
   independent review, a written rollback, and intentionally tiny capital.

## Implementation sequence

### Phase 1 — Make the control plane authoritative

- Persist pause/resume state and daily counters in SQLite so API, timers, MCP,
  and workers cannot each hold a different risk state.
- Route scheduled scans through the API or a shared service layer.
- Reject scans outside market hours unless explicitly forced.
- Replace zero-price “fills” with pending order records until a real fill price
  is available.
- Add structured event IDs and idempotency keys to every proposal/order.

**Exit criteria:** restarting any worker does not clear the kill switch or
duplicate an action; a paused API prevents the next scheduled proposal.

### Phase 2 — Make operations observable

- Add a `/readiness` endpoint that checks database, broker credentials,
  market-data freshness, disk space, and timer heartbeat.
- Add counters and timestamps for signals, proposals, rejects, submitted paper
  orders, fills, feed failures, and alert failures.
- Add daily reports for realized/unrealized P&L, drawdown, turnover, fees,
  exposure, data gaps, and strategy version.
- Add a tested backup/restore procedure for SQLite and reports.

**Exit criteria:** an operator can tell whether the system is safe to run from
one dashboard and one Telegram `/status` response.

### Phase 3 — Improve strategy quality without adding AI authority

- Keep deterministic `research_v001` as the baseline.
- Add versioned candidates with regime filters, volatility-aware sizing,
  position awareness, and explicit transaction-cost assumptions.
- Evaluate candidates on the same data slices with walk-forward validation and
  a holdout period.
- Use AI only for commentary, debugging, and experiment generation; it cannot
  set the ALLOW bit or change risk limits.

**Exit criteria:** each candidate has a reproducible run ID, config snapshot,
metrics table, and comparison against the baseline.

### Phase 4 — Usable paper automation

- Provide a setup/check command that validates environment, credentials,
  database, timers, alert routing, and paper mode.
- Keep `PAPER_AUTOMATION_ENABLED=false` until the shadow gate is signed off.
- Add a dry-run preview showing exactly which actions would be submitted.
- Add a two-step pause/resume confirmation in Telegram and rate limits for
  scans/reports.
- Make every scheduled job retry safely and avoid duplicate orders.

**Exit criteria:** run unattended on paper for a meaningful validation window
with zero unauthorized orders, no silent failures, and an auditable action
ledger.

### Phase 5 — Separate live-trading decision

Live execution is intentionally out of scope for the current implementation.
If considered later, it requires a separate broker adapter, separate secrets,
feature flag and deployment, independent risk service, manual approval,
position reconciliation, alert escalation, and a tested emergency shutdown.
Paper performance alone is not sufficient approval.

## Operating checklist

Before enabling paper automation:

```text
[ ] CI green on the exact commit
[ ] TRADING_MODE=paper
[ ] PAPER_AUTOMATION_ENABLED=true reviewed and documented
[ ] Alpaca paper account and data permissions verified
[ ] Risk limits and max notional reviewed
[ ] Kill switch tested from API and Telegram
[ ] Market-hours and stale-data behavior tested
[ ] Backups and alert delivery tested
[ ] One operator owns the rollback and daily review
```

## Success measures

Track engineering and risk outcomes separately from returns:

- unauthorized orders: **0**
- duplicate order attempts after retries/restarts: **0**
- unacknowledged critical alerts: **0**
- stale-data orders: **0**
- kill-switch recovery time
- proposal-to-fill and fill-to-reconciliation latency
- realized drawdown, exposure, turnover, fees, and slippage
