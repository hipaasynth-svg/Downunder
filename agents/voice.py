"""
Bar voice / style bible — the "voice lock".

The single source of truth for how the Down Under's marketing sounds. It is
injected into every agent's system prompt so command boards, captions, and
scripts come out on-voice and within responsible-alcohol rules, and off-voice
copy gets rejected before it reaches Cody.

Human-editable: the real content lives in ``VOICE_BIBLE.md`` at the repo root
(override the path with ``DOWNUNDER_VOICE_BIBLE``). Cody edits that file; the
condensed ``DEFAULT_VOICE_BIBLE`` below is only a fallback used when the file is
missing, so the agent always has a voice.

nooa-free and dependency-free, so it can be imported and tested without the
agent runtime or an API key.
"""

from __future__ import annotations

import os
from pathlib import Path

# Condensed fallback. The editable, fuller version is VOICE_BIBLE.md.
DEFAULT_VOICE_BIBLE = """\
# Bar Voice — Down Under (downtown Minot, ND)

WHO: A downtown Minot bar and e-tab lounge. Charitable gaming (e-tabs) is
sponsored by NDAD — playing supports North Dakotans with disabilities. A local
room where regulars know the bartender. On DrinkMinot as venue 63: tap the tag,
earn punches toward a free item, no app and no tracking.

VOICE: Plain, warm, local. Talk like a Minot bartender, not an ad. Short
sentences. The draw is the room, the people, and an honest reason to stop in —
never hype.

RESPONSIBLE-ALCOHOL RULES (never break):
- 21+. Never target minors, never imply underage drinking.
- Never say "drink more", push volume, glamorize getting drunk, or run
  drink-fast / beat-the-clock messaging. Promote the PLACE and the NIGHT.
- Charitable gaming: it's about supporting NDAD and having a good time, never
  "gamble more" or chasing a win.
- Include a light "please drink responsibly / grab a ride" nudge where it fits.

NEVER USE: "crazy", "insane", "get wasted", "turn up", "rager", ALL-CAPS hype,
emoji spam, fake scarcity, "must", countdown pressure.

ALWAYS TRUE (say when it fits): downtown Minot; e-tabs sponsored by NDAD;
locally run; on DrinkMinot (tap the tag by the register to earn punches).

MEASUREMENT: NO promo codes. Success is read from the nightly busy-ness log
(1-5 at close), DrinkMinot taps/click-throughs, and Google Business insights.
"""


def voice_bible_path() -> str:
    """Path to the editable voice bible (override via DOWNUNDER_VOICE_BIBLE)."""
    return os.environ.get("DOWNUNDER_VOICE_BIBLE", "VOICE_BIBLE.md")


def load_voice_bible(path: str | None = None) -> str:
    """Return the bar voice text.

    Reads ``VOICE_BIBLE.md`` (or ``path``) when present and non-empty; otherwise
    falls back to ``DEFAULT_VOICE_BIBLE``. Never raises — the agent must always
    have a voice.
    """
    target = Path(path or voice_bible_path())
    try:
        text = target.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return DEFAULT_VOICE_BIBLE
    return text or DEFAULT_VOICE_BIBLE
