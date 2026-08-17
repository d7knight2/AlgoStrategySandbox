"""Optional AI analysis via CLI (Grok / Gemini / Groq) — analysis only.

Safety:
  - Never executes shell from model output
  - Never places live trades
  - May propose structured RULE lines that the bot validates before applying

Keys (LibreChat on Pi often uses ~/librechat/.env):
  GOOGLE_KEY / GEMINI_API_KEY / GOOGLE_API_KEY  → Gemini
  GROQ_API_KEY                                   → Groq OpenAI-compatible
  XAI_API_KEY / GROK_API_KEY                     → xAI Grok HTTP
  AI_CLI=grok|gemini|groq|auto

CLI on this fleet: /home/d7knight/.local/bin/grok is present.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger("trading_core.ai_assist")

SYSTEM = (
    "You assist a PAPER-ONLY trading research bot. "
    "Data is delayed public STOCK Act / Form disclosures. "
    "Never recommend live trading. Be concise. "
    "If suggesting a copy rule, use exactly: RULE filer=Name budget=1000 side=buy"
)


def _load_dotenv_files() -> None:
    """Import LibreChat / alpaca env names without overriding existing os.environ."""
    candidates = [
        Path.home() / "librechat" / ".env",
        Path("/etc/alpaca/env"),
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ and val:
                os.environ[key] = val


_load_dotenv_files()

# LibreChat uses GOOGLE_KEY for Gemini
if not os.environ.get("GEMINI_API_KEY") and os.environ.get("GOOGLE_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_KEY"]
if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLE_KEY"]


def _which(names: list[str]) -> str | None:
    for n in names:
        path = shutil.which(n)
        if path:
            return path
    return None


def _run_cli(argv: list[str], timeout: float = 90.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "TERM": "dumb"},
        )
        out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
        if proc.returncode != 0 and not out:
            return {"ok": False, "error": f"exit {proc.returncode}"}
        return {"ok": True, "text": out[:3500], "provider_argv": argv[:2]}
    except FileNotFoundError:
        return {"ok": False, "error": "cli not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def _via_grok_cli(prompt: str) -> dict[str, Any]:
    bin_path = _which(["grok", "xai"])
    if not bin_path:
        return {"ok": False, "error": "grok CLI not installed"}
    return _run_cli([bin_path, prompt])


def _via_gemini_cli(prompt: str) -> dict[str, Any]:
    bin_path = _which(["gemini", "google-gemini"])
    if not bin_path:
        return {"ok": False, "error": "gemini CLI not installed"}
    return _run_cli([bin_path, "-p", prompt])


def _via_gemini_http(prompt: str) -> dict[str, Any]:
    key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_KEY")
        or ""
    )
    if not key:
        return {"ok": False, "error": "no GOOGLE_KEY / GEMINI_API_KEY"}
    try:
        import httpx

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent"
        )
        body = {"contents": [{"parts": [{"text": SYSTEM + "\n\nUser:\n" + prompt}]}]}
        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, params={"key": key}, json=body)
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            return {"ok": False, "error": str(data.get("error") or r.text)[:200]}
        parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
        text = "".join(str(p.get("text") or "") for p in parts).strip()
        if not text:
            return {"ok": False, "error": "empty model response"}
        return {"ok": True, "text": text[:3500], "provider": "gemini-http"}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def _via_groq_http(prompt: str) -> dict[str, Any]:
    """LibreChat custom endpoint style (OpenAI-compatible)."""
    key = os.environ.get("GROQ_API_KEY") or ""
    if not key:
        return {"ok": False, "error": "no GROQ_API_KEY"}
    try:
        import httpx

        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
            )
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            return {"ok": False, "error": str(data.get("error") or r.text)[:200]}
        text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        if not text:
            return {"ok": False, "error": "empty model response"}
        return {"ok": True, "text": str(text)[:3500], "provider": "groq-http"}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def _via_xai_http(prompt: str) -> dict[str, Any]:
    key = os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY") or ""
    if not key:
        return {"ok": False, "error": "no XAI_API_KEY"}
    try:
        import httpx

        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "grok-2-latest",
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
            )
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            return {"ok": False, "error": str(data.get("error") or r.text)[:200]}
        text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        if not text:
            return {"ok": False, "error": "empty model response"}
        return {"ok": True, "text": str(text)[:3500], "provider": "xai-http"}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def ask_ai(prompt: str, *, prefer: str | None = None) -> dict[str, Any]:
    prefer = (prefer or os.environ.get("AI_CLI") or "auto").lower()
    if prefer == "grok":
        order = ["grok_cli", "xai_http", "groq_http", "gemini_http", "gemini_cli"]
    elif prefer == "gemini":
        order = ["gemini_http", "gemini_cli", "groq_http", "grok_cli", "xai_http"]
    elif prefer == "groq":
        order = ["groq_http", "gemini_http", "grok_cli", "xai_http"]
    else:
        order = ["grok_cli", "gemini_http", "groq_http", "xai_http", "gemini_cli"]

    errors: list[str] = []
    dispatch = {
        "grok_cli": _via_grok_cli,
        "gemini_cli": _via_gemini_cli,
        "gemini_http": _via_gemini_http,
        "groq_http": _via_groq_http,
        "xai_http": _via_xai_http,
    }
    for name in order:
        res = dispatch[name](prompt)
        if res.get("ok") and res.get("text"):
            res["provider"] = res.get("provider") or name
            return res
        errors.append(f"{name}:{res.get('error')}")
    return {
        "ok": False,
        "error": (
            "No AI backend available. LibreChat keys usually live in ~/librechat/.env "
            "(GOOGLE_KEY, GROQ_API_KEY). Or set XAI_API_KEY / use grok CLI."
        ),
        "tried": errors,
    }


def analyze_context(title: str, payload: dict[str, Any] | str) -> dict[str, Any]:
    import json

    body = payload if isinstance(payload, str) else json.dumps(payload, default=str)[:2500]
    prompt = f"{title}\n\nData (paper research):\n{body}\n\nGive a short analysis (max 12 lines)."
    return ask_ai(prompt)


def key_status() -> dict[str, bool]:
    """Which backends look configured (no secret values)."""
    return {
        "grok_cli": bool(_which(["grok", "xai"])),
        "gemini_cli": bool(_which(["gemini", "google-gemini"])),
        "google_key": bool(
            os.environ.get("GOOGLE_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        ),
        "groq_key": bool(os.environ.get("GROQ_API_KEY")),
        "xai_key": bool(os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY")),
    }
