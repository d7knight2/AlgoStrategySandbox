---
name: unit-test-writing
description: Write and update Python unit tests for AlgoStrategySandbox without calling live AI APIs or burning Grok Gemini Groq quota. Use when adding tests, pytest, mocking network, conftest, or CI test policy.
---

# Unit test writing (no AI quota waste)

## Hard rule — never burn AI quota in tests

Unit tests **must not** call:

- xAI / Grok HTTP or `grok` CLI
- Gemini / `GOOGLE_KEY` / Google generateContent
- Groq chat completions
- LibreChat or any paid LLM endpoint
- Live Telegram `sendMessage` / `sendPhoto` (mock or skip)
- Live Alpaca order submit in unit tests (paper read mocks preferred)

If a module under test calls `ask_ai`, `analyze_context`, or CLI subprocesses, **monkeypatch** to a pure function that returns a fixed dict.

Prefer `pytest` + stdlib/`unittest.mock`. Keep tests offline and deterministic.

## When writing tests

1. Put tests under `python/tests/test_*.py`.
2. Use fixtures from `conftest.py` (AI/network blockers).
3. Test pure logic first (rules validation, formatters, risk limits).
4. Mock `httpx`, `subprocess.run`, `send_telegram`, broker clients.
5. Do **not** mark tests that need live keys as default unit tests — use `@pytest.mark.integration` and exclude from default CI if needed.
6. Never add `time.sleep` to wait on models.
7. Never log or assert full API keys.

## AI-related modules

| Module | Unit-test approach |
|--------|--------------------|
| `ai_assist.ask_ai` | Patch backends; assert fallback order / error shape |
| `cmd_ai` | Patch `ask_ai` → fixed text; assert HTML shape |
| `weekly_ai` / image gen | Mock providers; no real image model calls |
| Telegram notify | Mock `send_telegram` / `send_telegram_photo` |

## Pattern

```python
def test_ask_ai_uses_mock(monkeypatch):
    from src.notifications import ai_assist as m

    monkeypatch.setattr(m, "_via_grok_cli", lambda p: {"ok": True, "text": "OK", "provider": "mock"})
    monkeypatch.setattr(m, "_via_gemini_http", lambda p: {"ok": False, "error": "skip"})
    # disable others similarly or set prefer
    out = m.ask_ai("x", prefer="grok")
    assert out["ok"] is True
    assert "OK" in out["text"]
```

## Definition of done

- [ ] No real AI HTTP/CLI in the test path
- [ ] Passes with network disabled / no API keys
- [ ] Fast (seconds, not minutes)
- [ ] Does not require `XAI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_KEY`, `GROQ_API_KEY`
