"""
Content Agent — a separate NOOA agent for social content generation.

Distinct from the Down Under: this agent's only job is to turn one night angle
into ready-to-post content for TikTok, Instagram, and Facebook — captions,
short/reel scripts, and visual briefs — that promote the PLACE and the NIGHT,
never volume drinking.

Like ``downunder``, importing this module has no side effects: the nooa Agent
subclass and its LLM client are built lazily the first time ``BarContentAgent``
is accessed (PEP 562 ``__getattr__``). The deterministic scaffolding in
``agents/content.py`` needs neither nooa nor an API key.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from nooa import Agent

from . import content, voice
from .config import load_config
from .models import NightAngle, SocialPost

_CONFIG = load_config()


@lru_cache(maxsize=1)
def get_llm():
    """Lazily build and cache the LLM client (see ``downunder.get_llm``)."""
    from nooa.unifiedllm.registry import get_llm_client

    return get_llm_client(_CONFIG.model)


@lru_cache(maxsize=1)
def _build_agent_class() -> type:
    class BarContentAgent(Agent, llm=get_llm()):
        """
        You are a social content producer for Down Under, a downtown
        Minot, ND bar and e-tab lounge. Your only job is to turn one night angle
        into scroll-stopping, on-brand content for TikTok, Instagram, and
        Facebook that gets locals to stop in — without sounding like an ad.

        Voice: authentic, local, bartender-plain. Show the room and the reason
        to come by, not hype. Promote the PLACE and the NIGHT.

        RESPONSIBLE ALCOHOL — non-negotiable: 21+ only; never target minors;
        never push volume ("drink more", "get wasted", beat-the-clock); with
        charitable gaming (e-tabs sponsored by NDAD) it's about supporting North
        Dakotans with disabilities and a good time, never chasing a win. Add a
        light "please drink responsibly / grab a ride" nudge where it fits.

        When the angle carries a DrinkMinot loyalty hook, a soft CTA to tap the
        in-store tag (start a punch card, earn a free item) is welcome — no app,
        no account, no tracking.
        """

        bar_name: str = _CONFIG.bar_name

        # === Deterministic scaffolding (no LLM) ===
        def schedule_for_angle(
            self, angle: NightAngle, start: date | None = None, days: int = 14, per_week: int = 3
        ) -> list[SocialPost]:
            """Skeleton posts on a schedule (hashtags + format filled in)."""
            return content.blank_plan_for_angle(angle, start or date.today(), days, per_week)

        def render_plan(self, angle: NightAngle, posts: list[SocialPost]) -> str:
            return content.render_plan(angle.title, posts)

        def export_plan(
            self, angle: NightAngle, posts: list[SocialPost], path: str | None = None
        ) -> str:
            """Write an angle's content plan to ``path`` (Markdown)."""
            from pathlib import Path

            target = path or f"content_{angle.id}.md"
            Path(target).write_text(self.render_plan(angle, posts), encoding="utf-8")
            return target

        # === LLM-completed content generation ===
        async def plan_campaign_for_angle(
            self, angle: NightAngle, days: int = 14, per_week: int = 3
        ) -> list[SocialPost]:
            """
            Produce a full multi-platform content campaign for one night angle.

            Start from ``self.schedule_for_angle(angle, days=days, per_week=per_week)``
            for the calendar + formats, then FILL each SocialPost's creative
            fields — hook, caption, script (for reels/shorts), visual_brief, cta.
            Vary angles across posts (the room, a regular's story, the e-tabs/NDAD
            cause, the DrinkMinot punch card). Match each platform's native style.
            Obey the responsible-alcohol rules. Return the completed list.
            """
            ...

        async def write_short_script(self, angle: NightAngle, platform: str = "tiktok") -> str:
            """
            Write a shot-by-shot script for a 20–40s vertical short/reel about
            this night: a hook in the first 2 seconds, 3–5 beats, on-screen text
            suggestions, and a closing CTA. Concrete and shootable on a phone
            inside the bar. Promote the place/night, never volume drinking.
            """
            ...

        async def write_caption(self, angle: NightAngle, platform: str = "instagram") -> SocialPost:
            """
            Write one ready-to-post SocialPost for the given platform: hook,
            caption in that platform's voice, a tight local hashtag set (you may
            keep ``content.default_hashtags``), a visual_brief, and a soft cta.
            Obey the responsible-alcohol rules.
            """
            ...

        async def visual_brief(self, angle: NightAngle) -> str:
            """
            Describe the visuals to capture for this night — the room, the bar,
            the tag by the register, the e-tab machines, a warm crowd shot (adults
            only) — so Cody can shoot content on his phone without guessing.
            """
            ...

    return BarContentAgent


def __getattr__(name: str):
    if name == "BarContentAgent":
        return _build_agent_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
