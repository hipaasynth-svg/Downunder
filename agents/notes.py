"""
Bar memory helpers: Cody's notes inbox + the self-improvement playbook.

Two plain files, so they're inspectable and editable by a human:

* ``BAR_NOTES.md`` — Cody writes here to "talk to" the agent between runs. The
  agent reads it every run and honors it. (You edit it on the main branch.)
* ``PLAYBOOK.md`` — what the agent has learned about what works (which nights,
  which angles, which nudges move the busy-ness log and DrinkMinot taps). The
  agent appends to it each run (via ``reflect``) and reads it back next run, so
  it stops repeating what didn't work and doubles down on what did.

nooa-free and dependency-free, so it can be imported and unit-tested without the
agent runtime or an API key.
"""

from __future__ import annotations

import datetime
from pathlib import Path

# When BAR_NOTES.md still contains this seed marker, the inbox is "empty".
NOTES_PLACEHOLDER = "<!-- write-below -->"
PLAYBOOK_HEADER = "# Bar Playbook — what's working (auto-updated; prune freely)"


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""


def load_notes(path: str = "BAR_NOTES.md") -> str:
    """Cody's current note to the agent, or '' when the inbox is untouched."""
    text = _read(path)
    if not text or NOTES_PLACEHOLDER in text:
        return ""
    return text


def load_playbook(path: str = "PLAYBOOK.md") -> str:
    """The learned playbook text (empty string when there's none yet)."""
    return _read(path)


def append_playbook(text: str, path: str = "PLAYBOOK.md", *, today: str | None = None) -> bool:
    """Append dated learnings to the playbook. Returns True if it wrote anything.

    No-ops on empty text so a quiet run doesn't clutter the file.
    """
    text = (text or "").strip()
    if not text:
        return False
    day = today or datetime.date.today().isoformat()
    existing = _read(path) or PLAYBOOK_HEADER
    Path(path).write_text(f"{existing}\n\n## {day}\n{text}\n", encoding="utf-8")
    return True
