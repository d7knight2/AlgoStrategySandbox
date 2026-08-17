"""Shared pytest fixtures.

HARD RULE: unit tests must not burn AI quota (Grok / Gemini / Groq / LibreChat).
Do NOT globally mock send_telegram — tests/test_telegram.py exercises it with httpx mocks.
"""

from __future__ import annotations

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: may touch network or external services (not default unit)",
    )
    config.addinivalue_line(
        "markers",
        "ui: browser/playwright tests (optional)",
    )


@pytest.fixture(autouse=True)
def _block_ai_quota(request, monkeypatch):
    """Refuse live AI backends in non-integration tests.

    Does not patch Telegram send helpers (those are unit-tested with httpx mocks).
    """
    if request.node.get_closest_marker("integration"):
        return

    try:
        import src.notifications.ai_assist as ai

        def _no_ai(*_a, **_k):
            return {"ok": False, "error": "blocked-in-unit-test"}

        monkeypatch.setattr(ai, "_via_grok_cli", _no_ai)
        monkeypatch.setattr(ai, "_via_gemini_cli", _no_ai)
        monkeypatch.setattr(ai, "_via_gemini_http", _no_ai)
        monkeypatch.setattr(ai, "_via_groq_http", _no_ai)
        monkeypatch.setattr(ai, "_via_xai_http", _no_ai)

        # Prevent accidental subprocess AI CLIs
        import subprocess

        real_run = subprocess.run

        def _safe_run(argv, *a, **k):
            cmd0 = ""
            if argv and isinstance(argv, (list, tuple)) and argv:
                cmd0 = str(argv[0]).lower()
            banned = ("grok", "gemini", "xai", "claude", "cursor-agent")
            if any(b in cmd0 for b in banned):
                raise RuntimeError(
                    f"AI CLI blocked in unit tests: {cmd0}. Mock ask_ai instead."
                )
            return real_run(argv, *a, **k)

        monkeypatch.setattr(subprocess, "run", _safe_run)
    except Exception:
        pass
