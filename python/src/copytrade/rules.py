"""User-defined paper copy rules (any public filer).

Stored as JSON — editable via Telegram. Never live. AI may propose rules;
only validated fields are applied.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

RULES_PATH = Path(__file__).resolve().parents[2] / "data" / "reports" / "paper_copy_rules.json"

_MAX_BUDGET = 5_000.0
_MAX_LOOKBACK = 90
_FILER_RE = re.compile(r"^[A-Za-z0-9 .,'\-]{2,64}$")


def _default_rules() -> list[dict[str, Any]]:
    return [
        {
            "id": "pelosi-weekly-1000",
            "filer": "Nancy Pelosi",
            "weekly_budget": 1000.0,
            "side": "buy",  # buy | sell | both
            "enabled": True,
            "lookback_days": 14,
            "max_order": 1000.0,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "note": "default example",
        }
    ]


def load_rules() -> list[dict[str, Any]]:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not RULES_PATH.is_file():
        rules = _default_rules()
        save_rules(rules)
        return rules
    try:
        data = json.loads(RULES_PATH.read_text())
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return _default_rules()


def save_rules(rules: list[dict[str, Any]]) -> None:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(rules, indent=2, default=str))


def validate_rule(raw: dict[str, Any]) -> dict[str, Any]:
    filer = str(raw.get("filer") or "").strip()
    if not _FILER_RE.match(filer):
        raise ValueError("invalid filer name")
    side = str(raw.get("side") or "buy").lower()
    if side not in ("buy", "sell", "both"):
        raise ValueError("side must be buy|sell|both")
    budget = float(raw.get("weekly_budget") or 0)
    if budget < 25 or budget > _MAX_BUDGET:
        raise ValueError(f"weekly_budget must be 25–{_MAX_BUDGET:.0f}")
    lookback = int(raw.get("lookback_days") or 14)
    if lookback < 7 or lookback > _MAX_LOOKBACK:
        raise ValueError(f"lookback_days must be 7–{_MAX_LOOKBACK}")
    max_order = float(raw.get("max_order") or budget)
    max_order = min(max(25.0, max_order), budget, _MAX_BUDGET)
    return {
        "id": str(raw.get("id") or uuid.uuid4().hex[:10]),
        "filer": filer,
        "weekly_budget": round(budget, 2),
        "side": side,
        "enabled": bool(raw.get("enabled", True)),
        "lookback_days": lookback,
        "max_order": round(max_order, 2),
        "created_at": raw.get("created_at") or datetime.utcnow().isoformat() + "Z",
        "note": str(raw.get("note") or "")[:120],
    }


def add_rule(
    filer: str,
    *,
    weekly_budget: float = 1000.0,
    side: str = "buy",
    lookback_days: int = 14,
    max_order: float | None = None,
    note: str = "",
) -> dict[str, Any]:
    rule = validate_rule(
        {
            "filer": filer,
            "weekly_budget": weekly_budget,
            "side": side,
            "lookback_days": lookback_days,
            "max_order": max_order if max_order is not None else weekly_budget,
            "enabled": True,
            "note": note,
        }
    )
    rules = load_rules()
    # replace same filer+side if exists
    rules = [r for r in rules if not (r["filer"].lower() == rule["filer"].lower() and r["side"] == rule["side"])]
    rules.append(rule)
    save_rules(rules)
    return rule


def disable_rule(filer: str) -> int:
    rules = load_rules()
    n = 0
    needle = filer.lower().strip()
    for r in rules:
        if needle in r["filer"].lower() or r["filer"].lower() in needle:
            if r.get("enabled"):
                r["enabled"] = False
                n += 1
    save_rules(rules)
    return n


def enable_rule(filer: str) -> int:
    rules = load_rules()
    n = 0
    needle = filer.lower().strip()
    for r in rules:
        if needle in r["filer"].lower() or r["filer"].lower() in needle:
            r["enabled"] = True
            n += 1
    save_rules(rules)
    return n

def list_rules_text() -> str:
    rules = load_rules()
    if not rules:
        return "No paper copy rules. Example:\n<code>/rule Pelosi 1000 buy</code>"
    lines = ["<b>Paper copy rules</b>"]
    for r in rules:
        flag = "ON" if r.get("enabled") else "off"
        lines.append(
            f"• [{flag}] <b>{r['filer']}</b> "
            f"${r['weekly_budget']:.0f}/wk {r['side']} "
            f"lookback {r['lookback_days']}d "
            f"<code>{r['id']}</code>"
        )
    lines.append("<i>Paper only · public delayed PTRs · risk engine still applies</i>")
    return "\n".join(lines)
