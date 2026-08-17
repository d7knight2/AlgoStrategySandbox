"""Telegram: paper copy rules + AI analysis commands."""

from __future__ import annotations

import re
from typing import Any

from src.copytrade.rules import add_rule, disable_rule, enable_rule, list_rules_text, load_rules
from src.notifications.telegram import esc_html


def cmd_rules(arg: str = "") -> str:
    arg = (arg or "").strip()
    if not arg or arg.lower() in {"list", "ls", "show"}:
        return list_rules_text()
    return cmd_rule(arg)


def cmd_rule(arg: str) -> str:
    """/rule Pelosi 1000 buy  |  /rule off Tuberville  |  /rule on Pelosi"""
    parts = arg.split()
    if not parts:
        return (
            "<b>Paper rule</b>\n"
            "<code>/rule Pelosi 1000 buy</code> — $1000/wk copy buys\n"
            "<code>/rule Tuberville 500 both</code>\n"
            "<code>/rule off Pelosi</code> · <code>/rule on Pelosi</code>\n"
            "<code>/rules</code> — list\n"
            "<i>Paper only · public PTRs · risk engine on</i>"
        )
    low = parts[0].lower()
    if low in {"off", "disable", "stop"}:
        n = disable_rule(" ".join(parts[1:]) or "")
        return f"Disabled <code>{n}</code> rule(s)." if n else "No matching rule."
    if low in {"on", "enable", "start"}:
        n = enable_rule(" ".join(parts[1:]) or "")
        return f"Enabled <code>{n}</code> rule(s)." if n else "No matching rule."

    # Parse: Name [Name2…] [budget] [side]
    budget = 1000.0
    side = "buy"
    name_parts: list[str] = []
    for p in parts:
        if re.fullmatch(r"\d+(\.\d+)?", p):
            budget = float(p)
        elif p.lower() in ("buy", "sell", "both"):
            side = p.lower()
        else:
            name_parts.append(p)
    filer = " ".join(name_parts).strip()
    if not filer:
        return "Need a filer name. Example: <code>/rule Nancy Pelosi 1000 buy</code>"
    try:
        rule = add_rule(filer, weekly_budget=budget, side=side)
    except ValueError as exc:
        return f"<b>Rule rejected</b>\n<code>{esc_html(exc)}</code>"
    return (
        "<b>Paper rule saved</b>\n"
        f"Filer: <b>{esc_html(rule['filer'])}</b>\n"
        f"Budget: <code>${rule['weekly_budget']:.0f}</code>/week · side <code>{rule['side']}</code>\n"
        f"Id: <code>{rule['id']}</code>\n"
        "Runs on weekly allocate timer · paper only"
    )


def cmd_allocate(arg: str = "") -> str:
    """Manual run of weekly allocate."""
    from src.copytrade.weekly_allocate import run_all_rules

    propose = "propose" in (arg or "").lower() or "dry" in (arg or "").lower()
    report = run_all_rules(execute=not propose, notify=False)
    lines = [
        "<b>Allocate run</b> " + ("propose-only" if propose else "paper execute"),
        f"Rules: <code>{report.get('rules_run')}</code>",
    ]
    for block in report.get("results") or []:
        lines.append(
            f"• {esc_html(block.get('filer'))} "
            f"actions={len(block.get('actions') or [])} "
            f"spent=${float(block.get('spent') or 0):,.0f}"
        )
    lines.append("<i>Paper only</i>")
    return "\n".join(lines)


def cmd_ai(arg: str) -> str:
    """/ai [topic] — analysis only via Grok/Gemini CLI or API."""
    from src.copytrade.rules import load_rules
    from src.notifications.ai_assist import analyze_context, ask_ai

    topic = (arg or "").strip()
    if not topic:
        rules = load_rules()
        res = analyze_context(
            "Summarize current paper copy rules and suggest at most one new RULE line if useful.",
            {"rules": rules},
        )
    elif topic.lower().startswith("rule") or "suggest" in topic.lower():
        res = ask_ai(
            "User wants a paper copy rule suggestion. "
            f"Request: {topic}\n"
            "Reply with short rationale and one line: RULE filer=Name budget=1000 side=buy"
        )
    else:
        res = ask_ai(topic)

    if not res.get("ok"):
        return (
            "<b>AI unavailable</b>\n"
            f"<code>{esc_html(res.get('error'))}</code>\n"
            "Set <code>XAI_API_KEY</code> or <code>GEMINI_API_KEY</code>, "
            "or install <code>grok</code>/<code>gemini</code> CLI."
        )
    text = esc_html(res.get("text") or "")
    # Optional: apply RULE line if user said apply
    applied = ""
    if "apply" in topic.lower():
        m = re.search(
            r"RULE\s+filer=([^\s]+(?:\s+[^\s=]+)*)\s+budget=(\d+)\s+side=(buy|sell|both)",
            res.get("text") or "",
            re.I,
        )
        if m:
            try:
                rule = add_rule(m.group(1).strip(), weekly_budget=float(m.group(2)), side=m.group(3).lower())
                applied = f"\n\n<b>Applied</b> <code>{esc_html(rule['id'])}</code> {esc_html(rule['filer'])}"
            except ValueError as exc:
                applied = f"\n\n<b>Not applied</b> {esc_html(exc)}"
    provider = esc_html(res.get("provider") or "ai")
    return f"<b>AI · {provider}</b>\n{text}{applied}\n<i>Analysis only · paper research</i>"
