"""Unit tests for paper copy rules + AI assist (fully mocked — no AI quota)."""

from __future__ import annotations

import pytest


@pytest.fixture()
def rules_tmp(tmp_path, monkeypatch):
    path = tmp_path / "paper_copy_rules.json"
    monkeypatch.setattr("src.copytrade.rules.RULES_PATH", path)
    return path


def test_validate_and_add_rule(rules_tmp):
    from src.copytrade.rules import add_rule, load_rules, validate_rule

    r = validate_rule({"filer": "Nancy Pelosi", "weekly_budget": 1000, "side": "buy"})
    assert r["filer"] == "Nancy Pelosi"
    assert r["weekly_budget"] == 1000.0
    assert r["side"] == "buy"

    saved = add_rule("Tommy Tuberville", weekly_budget=500, side="both")
    assert saved["id"]
    rules = load_rules()
    assert any(x["filer"] == "Tommy Tuberville" for x in rules)
    assert rules_tmp.is_file()


def test_rule_rejects_bad_budget(rules_tmp):
    from src.copytrade.rules import validate_rule

    with pytest.raises(ValueError):
        validate_rule({"filer": "X", "weekly_budget": 1, "side": "buy"})


def test_rule_rejects_bad_side(rules_tmp):
    from src.copytrade.rules import validate_rule

    with pytest.raises(ValueError):
        validate_rule({"filer": "Pelosi", "weekly_budget": 100, "side": "long"})


def test_disable_enable_rule(rules_tmp):
    from src.copytrade.rules import add_rule, disable_rule, enable_rule, load_rules

    add_rule("Nancy Pelosi", weekly_budget=1000, side="buy")
    assert disable_rule("Pelosi") >= 1
    assert all(
        not r["enabled"] for r in load_rules() if "Pelosi" in r["filer"]
    )
    assert enable_rule("Pelosi") >= 1
    assert any(r["enabled"] for r in load_rules() if "Pelosi" in r["filer"])


def test_ask_ai_mocked_no_network(monkeypatch):
    from src.notifications import ai_assist as ai

    monkeypatch.setattr(
        ai,
        "_via_grok_cli",
        lambda prompt: {"ok": True, "text": "OK paper-only", "provider": "mock-grok"},
    )
    for name in (
        "_via_gemini_cli",
        "_via_gemini_http",
        "_via_groq_http",
        "_via_xai_http",
    ):
        monkeypatch.setattr(ai, name, lambda *_a, **_k: {"ok": False, "error": "skip"})

    out = ai.ask_ai("ping", prefer="grok")
    assert out["ok"] is True
    assert "OK" in out["text"]
    assert out.get("provider")


def test_ask_ai_fallback_message_without_keys(monkeypatch):
    from src.notifications import ai_assist as ai

    for name in (
        "_via_grok_cli",
        "_via_gemini_cli",
        "_via_gemini_http",
        "_via_groq_http",
        "_via_xai_http",
    ):
        monkeypatch.setattr(ai, name, lambda *_a, **_k: {"ok": False, "error": "none"})

    out = ai.ask_ai("ping")
    assert out["ok"] is False
    assert "error" in out


def test_cmd_rule_and_list(rules_tmp):
    from src.notifications.cmd_rules import cmd_rule, cmd_rules

    msg = cmd_rule("Nancy Pelosi 1000 buy")
    assert "Paper rule" in msg or "saved" in msg.lower()
    listing = cmd_rules("list")
    assert "Pelosi" in listing or "paper" in listing.lower()


def test_cmd_ai_uses_mock_not_quota(monkeypatch):
    from src.notifications import cmd_rules as cr

    monkeypatch.setattr(
        "src.notifications.ai_assist.ask_ai",
        lambda *_a, **_k: {"ok": True, "text": "analysis ok", "provider": "mock"},
    )
    monkeypatch.setattr(
        "src.notifications.ai_assist.analyze_context",
        lambda *_a, **_k: {"ok": True, "text": "summary ok", "provider": "mock"},
    )
    body = cr.cmd_ai("")
    assert "analysis" in body.lower() or "summary" in body.lower() or "AI" in body
    assert "unavailable" not in body.lower()


def test_key_status_no_secrets():
    from src.notifications.ai_assist import key_status

    st = key_status()
    assert isinstance(st, dict)
    for v in st.values():
        assert isinstance(v, bool)
