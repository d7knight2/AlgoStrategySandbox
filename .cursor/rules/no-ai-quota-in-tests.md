---
description: Unit tests must never call live AI APIs or burn Grok/Gemini/Groq quota
alwaysApply: true
---

# No AI quota in unit tests

When writing or running **unit tests** for this repo:

1. **Do not** call Grok, Gemini, Groq, LibreChat, or any LLM HTTP/CLI.
2. **Do not** use real `XAI_API_KEY`, `GOOGLE_KEY`, `GEMINI_API_KEY`, or `GROQ_API_KEY` in tests.
3. **Mock** `ask_ai`, `analyze_context`, `subprocess` for AI CLIs, and Telegram send helpers.
4. Use skill **unit-test-writing** (`.cursor/skills/unit-test-writing/SKILL.md`).
5. Live/integration checks are optional and must be marked `@pytest.mark.integration` — never default CI.

Violations waste paid/free-tier quota and make CI non-deterministic.
