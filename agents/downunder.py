"""
Down Under Agent — NOOA (NVIDIA Object-Oriented Agents)

Works for one bar (default: the Down Under, downtown Minot, ND). Its job is to
get more customers in the door tonight and this week, and to turn that foot
traffic into DrinkMinot loyalty taps. Uses Claude Opus 4.8 for creative /
marketing work.

It is a DAILY-PACKET ENGINE, not an autopilot: it reads the live DrinkMinot
loyalty state, produces a nightly brief a human can act on in minutes, and
learns from the busy-ness log. Nothing auto-publishes.

Install:
  pip install -r requirements.txt

Run (example):
  export ANTHROPIC_API_KEY=...
  python -m agents.run_nightly

Note: importing this module has no side effects. The nooa Agent subclass is
built lazily the first time ``DownunderAgent`` is accessed (PEP 562
``__getattr__``), and the LLM client is constructed at that same point — so the
data models and pure logic can be imported and tested without nooa, an API key,
or network access.
"""

from __future__ import annotations

from functools import lru_cache

from nooa import Agent

from . import (
    drink,
    events,
    local_events,
    logic,
    mail,
    notes,
    predicthq,
    voice,
    weather,
)
from .config import Config, load_config
from .models import (
    AgentState,
    BusynessEntry,
    BusynessRollup,
    Character,
    LocalEvent,
    NightAngle,
    TonightWeather,
    VenuePulse,
)
from .state import load_state, save_state

_CONFIG: Config = load_config()


# ---------- LLM ----------
@lru_cache(maxsize=1)
def get_llm():
    """Lazily build and cache the LLM client.

    Deferred so merely importing the package has no side effects and needs no
    ANTHROPIC_API_KEY; the client is constructed the first time the agent class
    is built (see ``_build_agent_class``).
    """
    from nooa.unifiedllm.registry import get_llm_client

    return get_llm_client(_CONFIG.model)


# ---------- Agent ----------
# The nooa metaclass consumes ``llm`` when the class is defined, so we build the
# class lazily inside a cached factory and expose it via module ``__getattr__``
# (PEP 562). Result: ``import agents`` / ``import agents.downunder`` has no
# side effects — the LLM client is only constructed the first time
# ``DownunderAgent`` is actually accessed.
@lru_cache(maxsize=1)
def _build_agent_class() -> type:
    class DownunderAgent(Agent, llm=get_llm()):
        """
        You are a bar marketing manager whose only job is to get more customers
        into Down Under — a downtown Minot, ND bar and e-tab lounge —
        tonight and this week, and to turn that foot traffic into DrinkMinot
        loyalty taps.

        You read the live DrinkMinot loyalty platform (the bar is venue id 63)
        to ground everything in real ratings, taps, and the punch-card reward —
        never guesses. A shopper taps the in-store tag at ``/?r=63`` to unlock a
        rating and a punch toward a free item; no app, no account, no tracking.

        Be direct, practical, and protective of Cody's limited time — he works
        the bar. Prefer one high-leverage move over many weak ones.

        RESPONSIBLE ALCOHOL — non-negotiable: 21+ only; never target minors;
        never push volume ("drink more", "get wasted", beat-the-clock);
        charitable gaming (e-tabs sponsored by NDAD) is about supporting North
        Dakotans with disabilities and a good time, never chasing a win. Promote
        the PLACE and the NIGHT. Add a light "please drink responsibly / grab a
        ride" nudge where it fits.

        MEASUREMENT: there are NO promo codes. Read success from the nightly
        busy-ness log (1-5 at close), DrinkMinot taps/click-throughs, and Google
        Business Profile insights — never invent numbers.

        VOICE LOCK: every word you write for the public — command boards,
        captions, scripts — MUST follow the bar voice bible in
        ``self.voice_bible`` (also appended below). If a line is off-voice or
        breaks a responsible-alcohol rule, rewrite it before it reaches Cody.
        """

        # === State ===
        # nooa's Agent is a plain object (not a pydantic model), so mutable state
        # is declared as bare annotations here and initialised per instance in
        # __init__; only immutable scalars keep class-level defaults.
        venue_pulse: VenuePulse | None
        angles: list[NightAngle]
        busyness_log: list[BusynessEntry]
        cast: list[Character]
        # Runtime-only (re-fetched each run, not persisted): forecast + events.
        tonight_weather: TonightWeather | None
        nearby_events: list[LocalEvent]
        minot_events: list[LocalEvent]

        focus_this_week: str = "turn tonight's foot traffic into DrinkMinot taps"
        weekly_goal: str = ""

        # The bar + its DrinkMinot listing.
        bar_name: str = _CONFIG.bar_name
        bar_city: str = _CONFIG.bar_city
        drink_url: str = _CONFIG.drink_url
        venue_id: int = _CONFIG.venue_id

        # Weather (api.weather.gov — free, no key) for the bar's town.
        weather_lat: float = _CONFIG.weather_lat
        weather_lon: float = _CONFIG.weather_lon

        # Nearby events (Ticketmaster Discovery — free key) search window.
        event_radius_miles: int = _CONFIG.event_radius_miles
        event_days_ahead: int = _CONFIG.event_days_ahead

        # Repo ownership (site changes ship only via PR).
        github_owner: str = _CONFIG.github_owner
        github_repo: str = _CONFIG.github_repo
        default_branch: str = _CONFIG.default_branch

        # Local state persistence
        state_path: str = _CONFIG.state_path

        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self.venue_pulse = None
            self.angles = logic.default_angles(self.tag_url())
            self.busyness_log = []
            self.cast = []
            self.tonight_weather = None
            self.nearby_events = []
            self.minot_events = []
            # Bar voice, loaded from VOICE_BIBLE.md (fallback baked in).
            self.voice_bible = voice.load_voice_bible()
            # Cody's between-run notes (BAR_NOTES.md); "" when the inbox is empty.
            self.bar_notes = notes.load_notes()

        # === Deterministic helpers (delegate to pure logic / drink reader) ===
        def tag_url(self) -> str:
            """The in-store DrinkMinot tag/QR link a customer taps (``/?r=63``)."""
            return f"{self.drink_url.rstrip('/')}/?r={self.venue_id}"

        def refresh_pulse(self) -> VenuePulse:
            """Read the live DrinkMinot loyalty state for this bar and remember it."""
            pulse = drink.fetch_pulse(self.drink_url, self.venue_id)
            self.venue_pulse = pulse
            return pulse

        def pulse_readout(self, pulse: VenuePulse | None = None) -> str:
            """Deterministic, honest loyalty readout (no LLM) for the brief."""
            p = pulse or self.venue_pulse
            if p is None:
                return "No DrinkMinot pulse read yet."
            return logic.render_pulse(p, drink_url=self.drink_url)

        def refresh_weather(self) -> TonightWeather:
            """Read tonight's forecast for the bar's town and remember it."""
            w = weather.fetch_tonight(self.weather_lat, self.weather_lon)
            self.tonight_weather = w
            return w

        def weather_readout(self, w: TonightWeather | None = None) -> str:
            """Deterministic one-line weather readout (no LLM) for the brief."""
            tw = w or self.tonight_weather
            if tw is None:
                return "No weather read yet."
            return weather.render_weather(tw)

        @property
        def has_events(self) -> bool:
            """True when a Ticketmaster key is configured (real events vs none)."""
            return events.configured()

        def refresh_events(self) -> list[LocalEvent]:
            """Read nearby events (Ticketmaster) and remember them."""
            self.nearby_events = events.fetch_events(
                self.weather_lat,
                self.weather_lon,
                radius_miles=self.event_radius_miles,
                days_ahead=self.event_days_ahead,
            )
            return self.nearby_events

        def events_readout(self, evs: list[LocalEvent] | None = None) -> str:
            """Deterministic readout of nearby events (no LLM) for the brief."""
            return events.render_events(
                self.nearby_events if evs is None else evs, city_hint=self.bar_city.split(",")[0]
            )

        @property
        def has_event_autosync(self) -> bool:
            """True when PredictHQ auto-sync can run (token + admin password set)."""
            import os

            return bool(predicthq.configured() and os.environ.get("DRINK_ADMIN_PASSWORD", "").strip())

        def sync_predicthq_events(self) -> dict:
            """Auto-populate the curated feed: pull PredictHQ events near the bar
            and upsert them into DrinkMinot /api/events under source 'predicthq'.

            Idempotent and source-scoped (never touches hand-curated events).
            No-ops (returns skipped) unless both PREDICTHQ_TOKEN and
            DRINK_ADMIN_PASSWORD are set.
            """
            import os

            admin = os.environ.get("DRINK_ADMIN_PASSWORD", "").strip()
            if not (predicthq.configured() and admin):
                return {"ok": False, "skipped": True}
            evs = predicthq.fetch_events(
                self.weather_lat,
                self.weather_lon,
                radius_miles=self.event_radius_miles,
                days_ahead=max(self.event_days_ahead, 14),
            )
            return local_events.sync_events(self.drink_url, admin, predicthq.SOURCE, evs)

        def refresh_minot_events(self) -> list[LocalEvent]:
            """Read our curated Minot events feed (DrinkMinot /api/events)."""
            self.minot_events = local_events.fetch_events(self.drink_url)
            return self.minot_events

        def minot_events_readout(self, evs: list[LocalEvent] | None = None) -> str:
            """Deterministic readout of curated Minot events (no LLM)."""
            return local_events.render_events(
                self.minot_events if evs is None else evs
            )

        def tonights_angle(self) -> NightAngle | None:
            """Tonight's promotable angle — weekday-specific if set, else rotating."""
            return logic.pick_tonight(self.angles)

        def record_busyness(self, date: str, score: int, note: str = "") -> BusynessEntry:
            """Log (or replace) a nightly 1-5 busy-ness reading."""
            entry = BusynessEntry(date=date, score=score, note=note)
            self.busyness_log = logic.upsert_busyness(self.busyness_log, entry)
            return entry

        def busyness_summary(self) -> BusynessRollup:
            return logic.busyness_rollup(self.busyness_log)

        def busyness_prompt(self, *, date: str = "") -> str:
            """The nightly ask to log tonight's 1-5, with recent context."""
            return logic.busyness_prompt(self.busyness_summary(), date=date)

        # === Send the nightly brief (Zoho Mail SMTP; needs ZOHO_MAIL_* env) ===
        def send_brief(self, to: str, subject: str, body: str) -> str:
            """Email a brief to Cody via Zoho Mail. Requires ZOHO_MAIL_* env."""
            mail.send_email(to, subject, body)
            return f"sent to {to}"

        # === State persistence ===
        def to_state(self) -> AgentState:
            return AgentState(
                venue_pulse=self.venue_pulse,
                angles=self.angles,
                busyness_log=self.busyness_log,
                cast=self.cast,
                focus_this_week=self.focus_this_week,
                weekly_goal=self.weekly_goal,
            )

        def apply_state(self, state: AgentState) -> None:
            self.venue_pulse = state.venue_pulse
            # Keep the seeded angles when a saved state carries none yet.
            self.angles = state.angles or logic.default_angles(self.tag_url())
            self.busyness_log = state.busyness_log
            self.cast = state.cast
            self.focus_this_week = state.focus_this_week
            self.weekly_goal = state.weekly_goal

        def save(self, path: str | None = None) -> None:
            save_state(self.to_state(), path or self.state_path)

        def load(self, path: str | None = None) -> None:
            self.apply_state(load_state(path or self.state_path))

        # === Core business methods (LLM-completed) ===
        async def nightly_command_board(self) -> str:
            """
            Produce a short, ruthless nightly command board for the bar.
            Max 8 lines. Ground it in ``self.venue_pulse``,
            ``self.tonight_weather`` (tonight's real forecast — cold/snow/storm
            means a quieter, regulars-only night; mild/clear means push for a
            crowd), ``self.minot_events`` (our curated Minot events) and
            ``self.nearby_events`` (Ticketmaster) — a big concert/game/fair in
            town tonight means crowds downtown, so be the before/after stop; a
            quiet night means you're the destination — and
            ``self.busyness_summary()`` — never invent numbers. Include:
            - One highest-leverage move to get people in TONIGHT (specific to the
              night, the weather, and to downtown Minot).
            - What to deliberately ignore.
            - The DrinkMinot loyalty pulse in one honest line (rating, taps, and
              — if persistence is off — that taps reset until Redis is attached).
            - Tonight's angle to lead with (from ``self.tonights_angle()``).
            - One concrete DrinkMinot-tap nudge to run at the bar tonight
              (e.g. "point three regulars to the tag by the register").
            Obey the voice lock and the responsible-alcohol rules.
            """
            ...

        async def loyalty_nudge(self) -> str:
            """
            Given ``self.venue_pulse``, write ONE short, concrete action Cody or a
            bartender can do at the bar tonight to earn more DrinkMinot taps /
            ratings — the honest way (show a regular where the tag is, mention the
            punch card when someone asks). 2-3 sentences, on voice. If the pulse
            shows persistence is off, say plainly that taps won't stick until the
            store is attached, and make tonight's nudge about the rating/visibility
            instead.
            """
            ...

        async def plan_tonight(self, angle: NightAngle) -> str:
            """
            Write a short floor plan for tonight built around ``angle``: the one
            reason to come in, what to say when it's slow, and the soft DrinkMinot
            tap moment — all things a working bartender can actually do. Keep it
            under ~8 lines, concrete, on voice, within the responsible-alcohol
            rules.
            """
            ...

        async def weekly_review(self) -> str:
            """
            Short weekly review grounded in the busy-ness log and DrinkMinot
            pulse: which nights are working, which angle pulled, what stalled,
            one adjusted focus, and one clear ask for Cody. No invented numbers.
            """
            ...

        # === Self-improvement ===
        async def reflect(self) -> str:
            """
            Review tonight's run and write down what to do differently next time.

            Look at: the DrinkMinot pulse (rating, taps, whether it's persistent),
            the busy-ness log (which weekday/angle scores best), which angle you
            led with, ``self.bar_notes`` (Cody's latest input), and the playbook
            already in your context. Then output 1-3 SHORT, concrete learnings —
            which night or angle is converting, a nudge worth repeating, what to
            stop. No fluff, at most 3 bullets. If nothing new was learned, return
            an empty string.

            Return ONLY the bullet lines (each starting with "- "); they are
            appended verbatim to the bar playbook.
            """
            ...

    # Bind the bar voice into the system prompt itself, so it applies to every
    # method whether or not nooa surfaces instance attributes. Read at
    # class-build time; VOICE_BIBLE.md edits take effect on the next run.
    doc = (DownunderAgent.__doc__ or "")
    doc += "\n\n===== BAR VOICE BIBLE (obey in all public copy) =====\n"
    doc += voice.load_voice_bible()
    # Each GitHub Actions run is a fresh process, so these files are re-read every
    # run: the agent starts each night already knowing what it learned and
    # whatever Cody wrote in the notes inbox.
    _playbook = notes.load_playbook()
    if _playbook:
        doc += (
            "\n\n===== BAR PLAYBOOK (what has worked — apply it, don't relearn it) =====\n"
            + _playbook
        )
    _notes = notes.load_notes()
    if _notes:
        doc += (
            "\n\n===== CODY'S NOTES FOR TONIGHT (honor these; they override defaults) =====\n"
            + _notes
        )
    DownunderAgent.__doc__ = doc
    return DownunderAgent


def __getattr__(name: str):
    # PEP 562: resolve ``DownunderAgent`` on first access, building the nooa
    # class (and LLM client) only then.
    if name == "DownunderAgent":
        return _build_agent_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
