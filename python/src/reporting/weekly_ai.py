"""Optional AI summary + image for weekly Telegram updates.

Uses Grok/Gemini when quota/keys exist; always fails soft back to
 deterministic text + matplotlib leaderboard chart.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any

from src.notifications.ai_assist import analyze_context, ask_ai

log = logging.getLogger("trading_core.reporting.weekly_ai")
REPORTS = Path(__file__).resolve().parents[2] / "data" / "reports"


def _compact(report: dict[str, Any]) -> dict[str, Any]:
    books = report.get("books") or []
    top = sorted(
        [b for b in books if b.get("return_pct") is not None],
        key=lambda b: float(b.get("return_pct") or 0),
        reverse=True,
    )[:6]
    return {
        "generated_at": report.get("generated_at"),
        "equity": (report.get("account") or {}).get("equity"),
        "week_return_pct": report.get("week_return_pct"),
        "unrealized_pl": report.get("unrealized_pl"),
        "ptr_week": report.get("ptr_week"),
        "top_books": [
            {
                "filer": b.get("filer"),
                "return_pct": b.get("return_pct"),
                "equity": b.get("equity"),
            }
            for b in top
        ],
        "position_count": len(report.get("positions") or []),
    }


def generate_weekly_ai_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Return {ok, text, provider} or soft failure."""
    if os.environ.get("WEEKLY_AI", "1").strip() in {"0", "false", "no"}:
        return {"ok": False, "error": "WEEKLY_AI disabled"}

    compact = _compact(report)
    prompt = (
        "Write a weekly PAPER trading research digest for Telegram.\n"
        "Rules: max 10 short lines, no live-trade advice, mention data is delayed public PTRs.\n"
        "Include: overall paper week return, notable filer books, one cautious insight.\n"
        f"Data JSON:\n{compact}"
    )
    res = analyze_context("Weekly paper portfolio digest", compact)
    if not res.get("ok"):
        # second try with explicit prompt
        res = ask_ai(prompt)
    if res.get("ok") and res.get("text"):
        return {
            "ok": True,
            "text": str(res["text"])[:2000],
            "provider": res.get("provider") or "ai",
        }
    return {"ok": False, "error": res.get("error") or "ai unavailable", "tried": res.get("tried")}


def _save_b64_image(b64: str, path: Path) -> Path | None:
    try:
        raw = base64.b64decode(b64)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path if path.is_file() and path.stat().st_size > 100 else None
    except Exception as exc:
        log.warning("save ai image failed: %s", type(exc).__name__)
        return None


def generate_weekly_ai_image(report: dict[str, Any]) -> dict[str, Any]:
    """Try Gemini / xAI image APIs; fail soft (no crash)."""
    if os.environ.get("WEEKLY_AI_IMAGE", "1").strip() in {"0", "false", "no"}:
        return {"ok": False, "error": "WEEKLY_AI_IMAGE disabled"}

    week_pct = report.get("week_return_pct")
    equity = (report.get("account") or {}).get("equity")
    prompt = (
        "Minimal dark fintech dashboard illustration, no readable logos, "
        "abstract green/red equity curve and subtle ranking bars, "
        f"mood for paper portfolio week return {week_pct}%, equity {equity}, "
        "professional, clean, 16:9, no text overlays"
    )

    # Gemini image (Imagen / native) — best-effort free tier
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    if key:
        try:
            import httpx

            # imagen-3.0 may require billing; fail soft on 403/429
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "imagen-3.0-generate-002:predict"
            )
            with httpx.Client(timeout=90.0) as client:
                r = client.post(
                    url,
                    params={"key": key},
                    json={"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}},
                )
            data = r.json() if r.content else {}
            if r.status_code < 400:
                preds = data.get("predictions") or []
                b64 = (preds[0] or {}).get("bytesBase64Encoded") if preds else None
                if b64:
                    path = _save_b64_image(b64, REPORTS / "weekly_ai_image.png")
                    if path:
                        return {"ok": True, "path": str(path), "provider": "gemini-imagen"}
            log.info("gemini image skipped status=%s", r.status_code)
        except Exception as exc:
            log.warning("gemini image error: %s", type(exc).__name__)

    # xAI image endpoint (if available on account)
    xkey = os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY") or ""
    if xkey:
        try:
            import httpx

            with httpx.Client(timeout=90.0) as client:
                r = client.post(
                    "https://api.x.ai/v1/images/generations",
                    headers={"Authorization": f"Bearer {xkey}"},
                    json={"model": "grok-2-image", "prompt": prompt, "n": 1},
                )
            data = r.json() if r.content else {}
            if r.status_code < 400:
                items = data.get("data") or []
                b64 = (items[0] or {}).get("b64_json") if items else None
                url_img = (items[0] or {}).get("url") if items else None
                if b64:
                    path = _save_b64_image(b64, REPORTS / "weekly_ai_image.png")
                    if path:
                        return {"ok": True, "path": str(path), "provider": "xai-image"}
                if url_img:
                    with httpx.Client(timeout=60.0) as c2:
                        img = c2.get(url_img)
                    if img.status_code == 200 and img.content:
                        path = REPORTS / "weekly_ai_image.png"
                        path.write_bytes(img.content)
                        return {"ok": True, "path": str(path), "provider": "xai-image-url"}
            log.info("xai image skipped status=%s", r.status_code)
        except Exception as exc:
            log.warning("xai image error: %s", type(exc).__name__)

    return {"ok": False, "error": "no image quota or unsupported model"}


def attach_weekly_ai(report: dict[str, Any]) -> dict[str, Any]:
    """Mutate report with ai_summary / ai_image fields."""
    summary = generate_weekly_ai_summary(report)
    report["ai_summary"] = summary
    image = generate_weekly_ai_image(report)
    report["ai_image"] = image
    return report


def format_weekly_ai_block(report: dict[str, Any]) -> str:
    s = report.get("ai_summary") or {}
    if not s.get("ok"):
        return ""
    text = str(s.get("text") or "").replace("&", "&").replace("<", "<").replace(">", ">")
    provider = str(s.get("provider") or "ai")
    return f"\n\n<b>AI insights · {provider}</b>\n{text}"
