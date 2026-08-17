"""Weekend / idle Telegram heartbeat."""

from __future__ import annotations

from typing import Any

from src.broker import AlpacaBroker
from src.notifications.telegram import format_heartbeat, send_telegram, telegram_configured
from src.risk import RiskEngine, RiskLimits


def run_heartbeat(*, notify: bool = True) -> dict[str, Any]:
    equity: Any = "—"
    paused = False
    try:
        acct = AlpacaBroker().get_account()
        equity = acct.get("equity", "—")
    except Exception as exc:
        equity = f"err:{exc}"[:40]
    try:
        paused = RiskEngine(RiskLimits()).limits.trading_paused
    except Exception:
        pass

    body = format_heartbeat(trading_paused=paused, equity=equity, weekday_timers=True)
    out: dict[str, Any] = {
        "equity": equity,
        "trading_paused": paused,
        "telegram_configured": telegram_configured(),
    }
    if notify and telegram_configured():
        out["telegram"] = send_telegram(body, disable_notification=True)
    return out


def main() -> None:
    import json

    print(json.dumps(run_heartbeat(), indent=2, default=str))


if __name__ == "__main__":
    main()
