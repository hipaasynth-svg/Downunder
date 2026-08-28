"""
Pure, deterministic business logic for the Bar Manager.

These functions take plain data and return plain data — no LLM calls, no
network, no nooa dependency — so they are cheap to reason about and easy to
unit-test. The agent delegates its non-judgment work here.
"""

from __future__ import annotations

import datetime
from typing import Any

from .models import (
    BusynessEntry,
    BusynessRollup,
    NightAngle,
    VenuePulse,
)

WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


# ---------- DrinkMinot pulse ----------
def _to_int(raw: Any) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _to_float(raw: Any) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def parse_pulse(state: dict[str, Any], venue_id: int) -> VenuePulse:
    """Extract one venue's live loyalty state from a ``GET /api/state`` payload.

    ``state`` is the JSON DrinkMinot returns: ``{persistent, restaurants:[...]}``.
    Each restaurant carries a computed ``rating`` plus counters and the owner's
    loyalty config. Returns an ``ok=False`` pulse (carrying ``error``) when the
    payload is malformed or the venue id isn't present, so callers never crash
    on a bad read.
    """
    if not isinstance(state, dict) or state.get("ok") is False:
        err = state.get("error", "state fetch failed") if isinstance(state, dict) else "bad state payload"
        return VenuePulse(id=venue_id, ok=False, error=str(err))

    restaurants = state.get("restaurants")
    if not isinstance(restaurants, list):
        return VenuePulse(id=venue_id, ok=False, error="no restaurants in state")

    row = None
    for r in restaurants:
        if isinstance(r, dict) and _to_int(r.get("id")) == venue_id:
            row = r
            break
    if row is None:
        return VenuePulse(id=venue_id, ok=False, error=f"venue {venue_id} not found")

    happy = row.get("happyHour")
    return VenuePulse(
        id=venue_id,
        name=str(row.get("name") or "").strip(),
        category=str(row.get("category") or "").strip(),
        address=str(row.get("address") or "").strip(),
        hours=str(row.get("hours") or "").strip(),
        rating=_to_float(row.get("rating")),
        rating_count=_to_int(row.get("ratingCount")),
        upvotes=_to_int(row.get("upvotes")),
        total_ratings=_to_int(row.get("totalRatings")),
        claimed=bool(row.get("claimed")),
        paid=bool(row.get("paid")),
        reward=str(row.get("reward") or "").strip(),
        coupon_valid_days=_to_int(row.get("couponValidDays")),
        happy_hour=happy if isinstance(happy, dict) else {},
        persistent=bool(state.get("persistent")),
        fetched_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        ok=True,
    )


def format_happy_hour(happy: dict[str, Any]) -> str:
    """A one-line human summary of a venue's happy-hour config, or '' if off."""
    if not isinstance(happy, dict) or not happy.get("enabled"):
        return ""
    start = str(happy.get("start") or "").strip()
    end = str(happy.get("end") or "").strip()
    special = str(happy.get("special") or "").strip()
    days = happy.get("days")
    when = f"{start}-{end}" if start and end else ""
    day_txt = ""
    if isinstance(days, list) and days:
        # DrinkMinot stores 0-6 (Sun..Sat in its UI); render short names.
        short = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        picked = [short[d] for d in days if isinstance(d, int) and 0 <= d < 7]
        day_txt = "".join(f"{d} " for d in picked).strip() if len(picked) < 7 else "daily"
    bits = [b for b in (day_txt, when, special) if b]
    return " · ".join(bits)


def render_pulse(pulse: VenuePulse, *, drink_url: str = "") -> str:
    """A deterministic, human-readable loyalty readout for the nightly brief.

    No LLM: just the honest numbers plus the one thing that decides whether the
    whole funnel is real tonight — is DrinkMinot persistent (Redis attached)?
    """
    if not pulse.ok:
        return f"DrinkMinot pulse unavailable: {pulse.error}"

    lines = [f"**{pulse.name or 'Venue'} on DrinkMinot** (id {pulse.id})"]
    rating_txt = f"{pulse.rating:.1f}★" if pulse.rating else "no rating yet"
    lines.append(
        f"- Rating: {rating_txt} from {pulse.rating_count} rating(s) · "
        f"{pulse.upvotes} upvote(s) · {pulse.total_ratings} total tap(s)"
    )
    claim = "claimed" if pulse.claimed else "UNCLAIMED — claim it to own the listing"
    paid = " · paid tier" if pulse.paid else ""
    lines.append(f"- Listing: {claim}{paid}")
    if pulse.reward:
        days = f" ({pulse.coupon_valid_days}-day coupon)" if pulse.coupon_valid_days else ""
        lines.append(f"- Reward: {pulse.reward}{days}")
    hh = format_happy_hour(pulse.happy_hour)
    if hh:
        lines.append(f"- Happy hour: {hh}")
    if drink_url:
        lines.append(f"- Tap tag: {pulse.tag_url(drink_url)}")
    if not pulse.persistent:
        lines.append(
            "- ⚠ DrinkMinot storage is NOT attached (persistent=false): taps and "
            "ratings reset on every cold start. Attach Upstash Redis before "
            "leaning on the punch card."
        )
    return "\n".join(lines)


# ---------- rotation ----------
def rotate_daily(items: list, n: int, day: int) -> list:
    """A deterministic daily window of ``n`` items that rotates by ``day``.

    Used so the nightly run leads with a different angle each day and covers the
    whole set across a cycle. Empty in → empty out; ``n`` is clamped to >= 1.
    """
    if not items:
        return []
    n = max(1, n)
    start = (day * n) % len(items)
    rotated = items[start:] + items[:start]
    return rotated[:n]


def promotable_angles(angles: list[NightAngle]) -> list[NightAngle]:
    return [a for a in angles if a.for_promo]


def angle_for_weekday(angles: list[NightAngle], weekday: str) -> NightAngle | None:
    """The angle explicitly tied to a weekday name, if any (case-insensitive)."""
    wd = (weekday or "").strip().lower()
    for a in angles:
        if a.day.strip().lower() == wd:
            return a
    return None


def pick_tonight(angles: list[NightAngle], *, date: datetime.date | None = None) -> NightAngle | None:
    """Choose tonight's angle: a weekday-specific one if set, else rotate.

    Deterministic for a given date, so the nightly run is reproducible.
    """
    promo = promotable_angles(angles)
    if not promo:
        return None
    date = date or datetime.date.today()
    weekday = WEEKDAYS[date.weekday()]
    specific = angle_for_weekday(promo, weekday)
    if specific is not None:
        return specific
    doy = date.timetuple().tm_yday
    window = rotate_daily(promo, 1, doy)
    return window[0] if window else None


# ---------- busy-ness log ----------
def upsert_busyness(
    log: list[BusynessEntry], entry: BusynessEntry
) -> list[BusynessEntry]:
    """Return a new log with ``entry`` added or replacing the same-date reading,
    kept sorted by date ascending."""
    kept = [e for e in log if e.date != entry.date]
    kept.append(entry)
    return sorted(kept, key=lambda e: e.date)


def recent_busyness(log: list[BusynessEntry], n: int = 7) -> list[BusynessEntry]:
    """The most recent ``n`` logged nights (score 1-5), newest last."""
    logged = [e for e in log if e.is_logged()]
    return logged[-max(0, n):]


def busyness_rollup(log: list[BusynessEntry]) -> BusynessRollup:
    """Summarize the busy-ness log: count, average, best weekday, last reading."""
    logged = [e for e in log if e.is_logged()]
    if not logged:
        return BusynessRollup()

    total = sum(e.score for e in logged)
    average = round(total / len(logged), 2)

    # Best weekday by average score.
    by_weekday: dict[str, list[int]] = {}
    for e in logged:
        try:
            wd = WEEKDAYS[datetime.date.fromisoformat(e.date).weekday()]
        except ValueError:
            continue
        by_weekday.setdefault(wd, []).append(e.score)
    best_weekday, best_avg = "", 0.0
    for wd, scores in by_weekday.items():
        avg = sum(scores) / len(scores)
        if avg > best_avg:
            best_weekday, best_avg = wd, round(avg, 2)

    last = max(logged, key=lambda e: e.date)
    return BusynessRollup(
        nights_logged=len(logged),
        average=average,
        best_weekday=best_weekday,
        best_weekday_average=best_avg,
        last_score=last.score,
        last_date=last.date,
    )


def busyness_prompt(rollup: BusynessRollup, *, date: str = "") -> str:
    """The nightly ask: log tonight's 1-5 at close, with recent context."""
    head = "# Busy-ness log"
    if date:
        head += f" — {date}"
    lines = [
        head,
        "",
        "At close, rate tonight 1 (dead) to 5 (packed). No promo codes — this "
        "gut score, DrinkMinot taps, and your Google Business insights are how "
        "we tell what actually worked.",
    ]
    if rollup.nights_logged:
        lines.append("")
        lines.append(
            f"So far: {rollup.nights_logged} night(s) logged, average "
            f"{rollup.average}/5."
        )
        if rollup.best_weekday:
            lines.append(
                f"Best night so far: {rollup.best_weekday} "
                f"(avg {rollup.best_weekday_average}/5)."
            )
        if rollup.last_date:
            lines.append(f"Last logged: {rollup.last_date} at {rollup.last_score}/5.")
    return "\n".join(lines) + "\n"


# ---------- seed angles ----------
def default_angles(loyalty_url: str = "") -> list[NightAngle]:
    """A starter set of promotable night angles for Down Under.

    Grounded in what the bar actually is — a downtown Minot e-tab lounge with
    charitable gaming sponsored by NDAD — and in DrinkMinot's punch-card loyalty
    hook. The LLM enriches the creative copy; these give it real anchors so it
    isn't inventing the bar. Edit freely; ``day`` ties an angle to a weekday.
    """
    return [
        NightAngle(
            id="etabs-ndad",
            title="E-tabs for a good cause",
            angle="Play e-tabs downtown and support North Dakotans with disabilities.",
            details=(
                "Charitable gaming is sponsored by NDAD — the money stays local. "
                "This is the honest, responsible draw: come hang out, play a little, "
                "do some good. Never 'play more' — just why it's worth a stop."
            ),
            reward="",
            cta="Come by after work — first round of e-tabs is more fun with a table.",
            loyalty_url=loyalty_url,
        ),
        NightAngle(
            id="tap-and-earn",
            title="Tap the tag, earn your reward",
            angle="Regulars: tap the DrinkMinot tag on the bar and start a punch card.",
            details=(
                "Every visit is a punch toward a free item — no app, no account, "
                "no tracking. Show a first-timer where the tag is on the bar."
            ),
            reward="Free item on a full punch card",
            cta="Ask the bartender to point out the tag by the register.",
            loyalty_url=loyalty_url,
        ),
        NightAngle(
            id="happy-hour",
            title="Downtown happy hour",
            angle="The after-work stop before the night gets going.",
            details=(
                "Lean, honest happy-hour draw — the special, the room, the fact "
                "that it's a walk from the rest of downtown Minot."
            ),
            reward="",
            cta="Swing in after work; grab a stool at the bar.",
            loyalty_url=loyalty_url,
        ),
        NightAngle(
            id="weekend-downtown",
            title="Start the weekend downtown",
            day="Friday",
            angle="Kick off the weekend at the Down Under before the crowd moves.",
            details=(
                "Payday-Friday energy, downtown Minot. A good first stop — then "
                "the rest of Main Street is right there."
            ),
            reward="",
            cta="Meet friends here first; tap the tag while you wait for your round.",
            loyalty_url=loyalty_url,
        ),
    ]
