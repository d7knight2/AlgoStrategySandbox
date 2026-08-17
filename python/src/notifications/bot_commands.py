"""Compatibility entrypoint for the Phase 1-2 unit name.

Prefer `python -m src.notifications.bot`. This module keeps
`python -m src.notifications.bot_commands` working with the same
chat-id allowlist and the full /track /gov /prefs command set.
"""

from __future__ import annotations

from src.notifications.bot import main
from src.notifications.commands import handle_text
from src.notifications.telegram import allowed_chat_id


def handle_command(text: str) -> str:
    """Run a slash command as the allowlisted chat (for tests / HTTP)."""
    return handle_text(text, chat_id=allowed_chat_id())


if __name__ == "__main__":
    main()
