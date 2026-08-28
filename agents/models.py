"""
Data models for the Bar Manager agent.

These are framework-agnostic (only depend on pydantic), so they can be
imported and unit-tested without the nooa runtime or an LLM.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class VenuePulse(BaseModel):
    """A read of one DrinkMinot venue's live loyalty state.

    Built by ``agents.drink`` from the public ``GET /api/state`` response (which
    never leaks passwords), so the nightly brief is grounded in the real
    ratings, upvotes, reward, and happy-hour the customer-facing site shows —
    not guesses.

    ``persistent`` mirrors DrinkMinot's own ``persistent`` flag: it is False
    until an Upstash Redis store is attached, meaning taps and ratings reset on
    every cold start. The agent reports this honestly rather than pretending the
    loyalty funnel is durable when it isn't.
    """

    model_config = ConfigDict(validate_assignment=True)

    id: int
    name: str = ""
    category: str = ""
    address: str = ""
    hours: str = ""
    # Loyalty signal.
    rating: float = 0.0  # rounded average the site displays
    rating_count: int = 0  # number of star ratings
    upvotes: int = 0
    total_ratings: int = 0
    # Owner-set loyalty config.
    claimed: bool = False
    paid: bool = False
    reward: str = ""  # what a full punch card earns
    coupon_valid_days: int = 0
    happy_hour: dict[str, Any] = Field(default_factory=dict)
    # Whether DrinkMinot has durable storage attached (taps survive overnight).
    persistent: bool = False
    # Read metadata.
    fetched_at: str = ""
    ok: bool = False
    error: str = ""

    def tag_url(self, drink_url: str) -> str:
        """The in-store tag/QR link a customer taps to unlock rating + a punch."""
        return f"{(drink_url or '').rstrip('/')}/?r={self.id}"


class NightAngle(BaseModel):
    """One promotable angle for a bar night — the "subject" the content agent
    writes about, the bar equivalent of an art piece.

    Deliberately light: a seed set lives in ``agents.logic`` and the LLM
    enriches the creative fields. A night can be a weekday theme, an event, or a
    standing draw (e-tabs for NDAD, happy hour, a game night).
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str
    title: str
    day: str = ""  # a weekday name, a date, or "" for evergreen
    angle: str = ""  # the hook: why come in tonight
    details: str = ""  # specifics — the draw, event, or charitable-gaming note
    reward: str = ""  # DrinkMinot punch/first-tap perk to mention, when set
    cta: str = ""  # soft call to action
    loyalty_url: str = ""  # the DrinkMinot tag link to tap in-store
    for_promo: bool = True  # actively promote this angle


Platform = Literal["tiktok", "instagram", "facebook"]
ContentFormat = Literal["post", "reel", "short", "story"]


class SocialPost(BaseModel):
    """One piece of social content for TikTok / Instagram / Facebook."""

    model_config = ConfigDict(validate_assignment=True)

    platform: Platform
    format: ContentFormat
    related_angle_id: str | None = None
    hook: str = ""  # the scroll-stopping first line / first 2 seconds
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    visual_brief: str = ""  # what to shoot / show (the "visuals")
    script: str = ""  # shot-by-shot script for reels / shorts
    cta: str = ""
    status: Literal["idea", "drafted", "scheduled", "posted"] = "idea"
    scheduled_for: str = ""  # ISO date, when scheduled


class BusynessEntry(BaseModel):
    """One nightly busy-ness reading, logged at close.

    DrinkMinot deliberately uses NO promo codes, so the honest measure of "did
    tonight work" is a simple 1-5 gut score at close, tracked over time. Paired
    with DrinkMinot click-throughs and Google Business Profile insights, it is
    the feedback loop the agent learns from.
    """

    model_config = ConfigDict(validate_assignment=True)

    date: str  # ISO date of the night
    score: int = 0  # 1 (dead) .. 5 (packed); 0 = not logged yet
    note: str = ""  # anything notable — weather, event, payday, hockey

    def is_logged(self) -> bool:
        return 1 <= self.score <= 5


class BusynessRollup(BaseModel):
    """A deterministic summary of recent busy-ness readings."""

    nights_logged: int = 0
    average: float = 0.0
    best_weekday: str = ""  # weekday with the highest average score
    best_weekday_average: float = 0.0
    last_score: int = 0
    last_date: str = ""


# ---------- Weather ----------
class TonightWeather(BaseModel):
    """Tonight's forecast for the bar's town, from the US National Weather
    Service (``api.weather.gov`` — free, no key). Weather is one of the biggest
    predictors of who goes out, so the nightly brief factors it in.

    Built by ``agents.weather`` from the real NWS forecast periods; an
    ``ok=False`` value (carrying ``error``) means the read failed and the brief
    should carry on without it.
    """

    model_config = ConfigDict(validate_assignment=True)

    city: str = ""  # e.g. "Minot, ND"
    period: str = ""  # NWS period name, e.g. "Tonight"
    temperature: int | None = None
    temp_unit: str = "F"
    short_forecast: str = ""  # e.g. "Partly Cloudy"
    detailed_forecast: str = ""
    precip_chance: int | None = None  # percent, when NWS provides it
    wind: str = ""  # e.g. "NW 10 mph"
    is_daytime: bool = False
    rough: bool = False  # heuristic: snow/storm/ice/bitter cold — expect a quieter night
    fetched_at: str = ""
    ok: bool = False
    error: str = ""


# ---------- Local events ----------
class LocalEvent(BaseModel):
    """One nearby event from the Ticketmaster Discovery API.

    A big concert, game, or fair downtown fills the bars around it — so the
    nightly brief lists what's happening near Minot and flags anything tonight.
    Built by ``agents.events``; purely informational.
    """

    model_config = ConfigDict(validate_assignment=True)

    name: str
    date: str = ""  # local date, YYYY-MM-DD
    time: str = ""  # local start time, HH:MM when known
    venue: str = ""
    city: str = ""
    category: str = ""  # e.g. "Music", "Sports"
    url: str = ""
    is_tonight: bool = False


# ---------- Cartoons ----------
class Character(BaseModel):
    """One recurring cast member for the Down Under cartoons.

    The agent invents the cast (``ComicAgent.invent_cast``) and remembers it in
    state, so the same characters recur strip after strip. ``look`` is the
    visual description that keeps a character on-model; ``reference_path`` points
    at the character's locked "canon" image once generated — the field the image
    model is fed on every future strip so the character stays consistent. Empty
    ``reference_path`` means art hasn't been rendered yet (text-only mode).
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str
    name: str
    role: str = ""  # e.g. "bartender", "regular", "e-tab mascot"
    look: str = ""  # visual description (species/build/clothes/colors) for consistency
    personality: str = ""
    catchphrase: str = ""
    reference_path: str = ""  # path to the locked canon image, "" until rendered


class ComicPanel(BaseModel):
    """One panel of a cartoon strip."""

    model_config = ConfigDict(validate_assignment=True)

    scene: str = ""  # what's happening / the setting
    speaker: str = ""  # character id or name delivering the line
    line: str = ""  # the dialogue for the speech bubble


class ComicStrip(BaseModel):
    """A short cartoon strip about a Down Under night.

    Written by the LLM from a ``NightAngle`` + the cast, then rendered as one
    multi-panel image (see ``agents.cartoon`` / ``agents.gemini``). ``image_path``
    is the rendered PNG, or "" when it was produced as a text storyboard only.
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str
    title: str
    angle_id: str = ""
    characters: list[str] = Field(default_factory=list)  # character ids featured
    panels: list[ComicPanel] = Field(default_factory=list)
    caption: str = ""  # the social caption to post with the strip
    image_path: str = ""  # rendered strip PNG, "" if text-only


class AgentState(BaseModel):
    """Serializable snapshot of the agent's mutable business state."""

    venue_pulse: VenuePulse | None = None
    angles: list[NightAngle] = Field(default_factory=list)
    busyness_log: list[BusynessEntry] = Field(default_factory=list)
    cast: list[Character] = Field(default_factory=list)
    focus_this_week: str = "turn tonight's foot traffic into DrinkMinot taps"
    weekly_goal: str = ""
