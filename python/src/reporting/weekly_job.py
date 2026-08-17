"""CLI entry for weekly timer: report + AI insights + charts."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.notifications.telegram import esc_html
from src.reporting.weekly import generate_weekly_report
from src.reporting.weekly_notify import send_weekly_package

log = logging.getLogger("trading_core.reporting.weekly_job")


def format_weekly_body(report: dict[str, Any]) -> str:
    """Deterministic HTML body (AI block appended by send_weekly_package)."""
    acct = report.get("account") or {}
    equity = acct.get("equity", "—")
    week_pct = report.get("week_return_pct")
    pct_s = f"{week_pct:+.2f}%" if week_pct is not None else "—"
    ptr = report.get("ptr_week") or {}
    books = report.get("books") or []
    top = sorted(
        books,
        key=lambda b: float(b.get("return_pct") or -1e9),
        reverse=True,
    )[:5]

    lines = [
        "<b>Weekly paper recap</b>",
        f"Equity <code>${esc_html(equity)}</code> · week <code>{esc_html(pct_s)}</code>",
        f"PTR window: buys={ptr.get('buys', 0)} sells={ptr.get('sells', 0)} "
        f"copied={ptr.get('copied', 0)}",
        "",
        "<b>Top paper books</b>",
    ]
    if not top:
        lines.append("None yet — /rule or /track a filer")
    for b in top:
        ret = b.get("return_pct")
        ret_s = f"{float(ret):+.1f}%" if ret is not None else "—"
        lines.append(
            f"• {esc_html(b.get('filer'))} {esc_html(ret_s)} · "
            f"${esc_html(b.get('equity'))}"
        )
    lines.append("")
    lines.append("<i>Paper only · delayed public filings · not advice</i>")
    return "\n".join(lines)


def run(*, notify: bool = True) -> dict[str, Any]:
    report = generate_weekly_report(notify=False)
    if notify:
        # Prefer prefs flag if present on report path — generate_weekly_report
        # already computed weekly_on internally when notify=True; we send always
        # when caller asks notify, but respect telegram package.
        report["telegram"] = send_weekly_package(report, body_html=format_weekly_body(report))
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    report = run(notify=True)
    print(json.dumps(
        {
            "generated_at": report.get("generated_at"),
            "week_return_pct": report.get("week_return_pct"),
            "ai_summary_ok": (report.get("ai_summary") or {}).get("ok"),
            "telegram": report.get("telegram"),
        },
        indent=2,
        default=str,
    ))


if __name__ == "__main__":
    main()
