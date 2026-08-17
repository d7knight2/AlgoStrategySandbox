"""Prometheus metrics for the trading core (optional dependency)."""

from __future__ import annotations

from typing import Any

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

    _PROM = True
except Exception:  # pragma: no cover
    _PROM = False
    CONTENT_TYPE_LATEST = "text/plain; charset=utf-8"

if _PROM:
    SCANS = Counter("trading_research_scans_total", "Research universe scans")
    TELEGRAM_OK = Counter("trading_telegram_sent_total", "Successful Telegram sends")
    TELEGRAM_FAIL = Counter("trading_telegram_failed_total", "Failed Telegram sends")
    RISK_ALLOW = Counter("trading_risk_allow_total", "Risk ALLOW decisions")
    RISK_REJECT = Counter("trading_risk_reject_total", "Risk REJECT decisions")
    PAUSED = Gauge("trading_paused", "1 if kill switch active")
    EQUITY = Gauge("trading_paper_equity", "Paper account equity when last observed")
else:  # pragma: no cover
    SCANS = TELEGRAM_OK = TELEGRAM_FAIL = RISK_ALLOW = RISK_REJECT = PAUSED = EQUITY = None


def note_scan() -> None:
    if _PROM and SCANS is not None:
        SCANS.inc()


def note_telegram(sent: bool) -> None:
    if not _PROM:
        return
    if sent and TELEGRAM_OK is not None:
        TELEGRAM_OK.inc()
    elif TELEGRAM_FAIL is not None:
        TELEGRAM_FAIL.inc()


def note_risk(decision: str) -> None:
    if not _PROM:
        return
    if decision == "ALLOW" and RISK_ALLOW is not None:
        RISK_ALLOW.inc()
    elif decision == "REJECT" and RISK_REJECT is not None:
        RISK_REJECT.inc()


def set_paused(paused: bool) -> None:
    if _PROM and PAUSED is not None:
        PAUSED.set(1 if paused else 0)


def set_equity(value: float) -> None:
    if _PROM and EQUITY is not None:
        EQUITY.set(value)


def render_metrics() -> tuple[bytes, str]:
    if not _PROM:
        return b"# prometheus_client not installed\n", "text/plain; charset=utf-8"
    return generate_latest(), CONTENT_TYPE_LATEST


def metrics_enabled() -> bool:
    return _PROM
