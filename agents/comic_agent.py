"""
Comic Agent — a separate NOOA agent for the Down Under cartoons.

Two jobs: (1) invent and remember a small RECURRING cast for the bar, and
(2) write a short cartoon strip about tonight's angle using that cast. The actual
drawing is done by ``agents/gemini.py``; the consistent-character technique
(one locked reference image per character, reused every strip) is orchestrated
by the nightly runner.

Like the other agents, importing this module has no side effects: the nooa Agent
subclass and its LLM client are built lazily the first time ``ComicAgent`` is
accessed (PEP 562 ``__getattr__``). The deterministic prompt/scaffolding logic in
``agents/cartoon.py`` needs neither nooa nor an API key.
"""

from __future__ import annotations

from functools import lru_cache

from nooa import Agent

from . import cartoon, voice
from .config import load_config
from .models import Character, ComicStrip, NightAngle

_CONFIG = load_config()


@lru_cache(maxsize=1)
def get_llm():
    """Lazily build and cache the LLM client (see ``downunder.get_llm``)."""
    from nooa.unifiedllm.registry import get_llm_client

    return get_llm_client(_CONFIG.model)


@lru_cache(maxsize=1)
def _build_agent_class() -> type:
    class ComicAgent(Agent, llm=get_llm()):
        """
        You are a cartoonist for Down Under, a downtown Minot, ND bar and e-tab
        lounge. You do two things: invent a small, lovable RECURRING cast for the
        bar, and write short, funny cartoon strips about the night — the kind a
        local would tag a friend in.

        Keep the humor warm and small-town, never mean or edgy. The strips
        promote the PLACE and the NIGHT and, when it fits, a soft nudge to tap
        the DrinkMinot tag on the bar.

        RESPONSIBLE ALCOHOL — non-negotiable: every character is an adult (21+);
        never depict or imply minors; never show drunkenness or push volume
        drinking; e-tabs / charitable gaming are about supporting North Dakotans
        with disabilities (NDAD) and a good time, never chasing a win.

        VOICE LOCK: follow the bar voice bible in ``self.voice_bible`` (appended
        below). Rewrite any line that is off-voice or breaks a rule above.
        """

        bar_name: str = _CONFIG.bar_name

        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self.voice_bible = voice.load_voice_bible()

        # === Deterministic helpers (no LLM) — prompt building ===
        def character_reference_prompt(self, char: Character) -> str:
            return cartoon.character_reference_prompt(char)

        def strip_image_prompt(self, strip: ComicStrip, cast: list[Character]) -> str:
            return cartoon.strip_image_prompt(strip, cast)

        # === LLM-completed creative work ===
        async def invent_cast(self) -> list[Character]:
            """
            Invent a small recurring cast (2-3 characters) for Down Under.

            Good candidates: a deadpan veteran bartender, a lucky-charm e-tab
            regular, a friendly bar mascot. For each Character fill: a short id
            (lowercase, no spaces), name, role, a SPECIFIC and consistent
            ``look`` (species/build, clothes, colors, distinguishing features —
            detailed enough to redraw identically every time), a one-line
            personality, and a catchphrase. Adults only, on voice. Return the
            list; leave ``reference_path`` empty (art is rendered later).
            """
            ...

        async def write_strip(self, angle: NightAngle, cast: list[Character]) -> ComicStrip:
            """
            Write a short 3-panel cartoon strip about tonight (grounded in
            ``angle``) starring one or more of ``cast``.

            Fill the ComicStrip: a short id, a title, ``angle_id`` = angle.id,
            ``characters`` = the ids of the cast members used, 3 ``panels`` (each
            with a scene, the speaker's id, and a short line of dialogue), and a
            ``caption`` = the social caption to post with the strip. Land a small,
            warm joke; a light DrinkMinot-tap nudge is welcome when it fits.
            Obey the voice lock and the responsible-alcohol rules.
            """
            ...

    return ComicAgent


def __getattr__(name: str):
    if name == "ComicAgent":
        return _build_agent_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
