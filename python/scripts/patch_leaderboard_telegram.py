"""One-shot patch: send_telegram_photo + /leaderboard command + weekly hook."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_telegram() -> None:
    p = ROOT / "src" / "notifications" / "telegram.py"
    t = p.read_text()
    if "def send_telegram_photo" in t:
        print("telegram: send_telegram_photo already present")
        return
    snippet = '''

def send_telegram_photo(
    image_path,
    *,
    caption: str | None = None,
    parse_mode: str | None = "HTML",
) -> dict[str, Any]:
    """Send a local image via sendPhoto. Never logs the bot token URL."""
    from pathlib import Path as _Path

    token = getattr(settings, "telegram_bot_token", "") or ""
    chat_id = getattr(settings, "telegram_chat_id", "") or ""
    if not token or not chat_id:
        return {"sent": False, "reason": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"}

    path = _Path(image_path)
    if not path.is_file():
        return {"sent": False, "error": f"missing image: {path}"}

    url = f"{TELEGRAM_API}/bot{token}/sendPhoto"
    data: dict[str, Any] = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption[:1024]
        if parse_mode:
            data["parse_mode"] = parse_mode

    try:
        _throttle()
        with path.open("rb") as fh:
            files = {"photo": (path.name, fh, "image/png")}
            with httpx.Client(timeout=60.0) as client:
                r = client.post(url, data=data, files=files)
        payload = r.json() if r.content else {}
        if r.status_code != 200 or not payload.get("ok"):
            err = payload.get("description") or r.text[:300]
            log.warning("telegram photo failed status=%s error=%s", r.status_code, err)
            return {"sent": False, "status_code": r.status_code, "error": err}
        mid = (payload.get("result") or {}).get("message_id")
        log.info("telegram photo ok message_id=%s", mid)
        return {"sent": True, "message_id": mid}
    except Exception as e:
        log.warning("telegram photo exception type=%s", type(e).__name__)
        return {"sent": False, "error": str(e)[:200], "error_type": type(e).__name__}

'''
    if "def format_scan_alert" in t:
        t = t.replace("def format_scan_alert", snippet + "\ndef format_scan_alert", 1)
    elif "def format_heartbeat" in t:
        t = t.replace("def format_heartbeat", snippet + "\ndef format_heartbeat", 1)
    else:
        t = t + snippet
    p.write_text(t)
    print("telegram: added send_telegram_photo")


def patch_commands() -> None:
    p = ROOT / "src" / "notifications" / "commands.py"
    t = p.read_text()
    if "def _cmd_leaderboard" in t:
        print("commands: leaderboard already present")
        return

    t = t.replace(
        "/books\n/book Pelosi",
        "/books\n/book Pelosi\n/leaderboard — ranked paper books + chart image",
        1,
    )
    t = t.replace(
        'if cmd == "/books":\n        return _cmd_books()',
        'if cmd in {"/leaderboard", "/lb"}:\n        return _cmd_leaderboard()\n'
        '    if cmd == "/books":\n        return _cmd_books()',
        1,
    )
    fn = '''

def _cmd_leaderboard() -> str:
    """Send ranked table + PNG photo to the chat."""
    from src.notifications.leaderboard_notify import send_leaderboard_update

    result = send_leaderboard_update(fetch_prices=True, weekly=False)
    if result.get("sent"):
        return (
            "<b>Leaderboard sent</b>\n"
            f"books: <code>{result.get('count', 0)}</code>\n"
            "<i>Chart image above · paper only</i>"
        )
    err = (result.get("photo") or {}).get("error") or result.get("reason") or "send failed"
    return f"<b>Leaderboard failed</b>\n<code>{esc_html(err)}</code>"

'''
    if "def _cmd_books" in t:
        t = t.replace("def _cmd_books", fn + "\ndef _cmd_books", 1)
    else:
        t += fn

    t = t.replace(
        'if "status" in lower or "health" in lower or "equity" in lower:\n        return "/status"',
        'if "leaderboard" in lower or lower in {"lb", "ranks", "ranking"}:\n        return "/leaderboard"\n'
        '    if "status" in lower or "health" in lower or "equity" in lower:\n        return "/status"',
        1,
    )
    p.write_text(t)
    print("commands: /leaderboard wired")


def patch_weekly() -> None:
    p = ROOT / "src" / "reporting" / "weekly.py"
    if not p.exists():
        print("weekly.py missing")
        return
    t = p.read_text()
    if "send_leaderboard_update" in t:
        print("weekly: already sends leaderboard")
        return
    hook = '''
    # Leaderboard chart (weekly image update)
    try:
        from src.notifications.leaderboard_notify import send_leaderboard_update

        if notify and weekly_on:
            report["leaderboard_telegram"] = send_leaderboard_update(
                fetch_prices=True, weekly=True
            )
    except Exception as _lb_exc:
        log.warning("weekly leaderboard image failed: %s", type(_lb_exc).__name__)
        report["leaderboard_telegram"] = {"sent": False, "error": type(_lb_exc).__name__}

'''
    idx = t.rfind("return report")
    if idx < 0:
        print("weekly: could not find return report")
        return
    t = t[:idx] + hook + "    " + t[idx:]
    p.write_text(t)
    print("weekly: leaderboard image hook added")


if __name__ == "__main__":
    patch_telegram()
    patch_commands()
    patch_weekly()
    print("done")
