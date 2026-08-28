"""
Nearby events from the Ticketmaster Discovery API (free key).

A big concert, game, or fair near downtown fills the surrounding bars — so the
nightly brief lists what's happening near Minot and flags anything TONIGHT. This
is the honest, free first pass at the "predict big nights" idea; PredictHQ is the
paid upgrade for attendance-ranked, non-ticketed demand intelligence.

Enabled by ``TICKETMASTER_API_KEY`` (free at developer.ticketmaster.com). With no
key it degrades gracefully: ``configured()`` is False and ``fetch_events()``
returns ``[]`` instead of raising.

API (Discovery v2):
  GET https://app.ticketmaster.com/discovery/v2/events.json
      ?apikey=<key>&latlong=<lat>,<lon>&radius=<mi>&unit=miles
      &startDateTime=<UTC ISO Z>&endDateTime=<UTC ISO Z>&sort=date,asc&size=<n>
  events at: _embedded.events[]  (name, url, dates.start.localDate/localTime,
             classifications[0].segment.name, _embedded.venues[0].name/city)

Dependency-free (stdlib ``urllib``).
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import LocalEvent

_ENDPOINT = "https://app.ticketmaster.com/discovery/v2/events.json"
_USER_AGENT = "DownunderAgent/0.1 (+https://drinkminot.com)"


def api_key() -> str:
    return os.environ.get("TICKETMASTER_API_KEY", "").strip()


def configured() -> bool:
    """True when a Ticketmaster key is available (real events vs none)."""
    return bool(api_key())


def _utc_z(dt: datetime.datetime) -> str:
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_events(payload: dict[str, Any], *, today: str = "") -> list[LocalEvent]:
    """Parse a Discovery ``events.json`` response into LocalEvent rows. Pure.

    ``today`` (ISO date) flags events happening tonight. Malformed entries are
    skipped rather than raising.
    """
    out: list[LocalEvent] = []
    if not isinstance(payload, dict):
        return out
    events = payload.get("_embedded", {}).get("events", []) if isinstance(payload.get("_embedded"), dict) else []
    for e in events or []:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name") or "").strip()
        if not name:
            continue
        dates = e.get("dates", {}) if isinstance(e.get("dates"), dict) else {}
        start = dates.get("start", {}) if isinstance(dates.get("start"), dict) else {}
        date = str(start.get("localDate") or "").strip()
        time = str(start.get("localTime") or "").strip()[:5]  # HH:MM

        venue_name, city = "", ""
        emb = e.get("_embedded", {}) if isinstance(e.get("_embedded"), dict) else {}
        venues = emb.get("venues", []) if isinstance(emb.get("venues"), list) else []
        if venues and isinstance(venues[0], dict):
            venue_name = str(venues[0].get("name") or "").strip()
            city = str((venues[0].get("city") or {}).get("name") or "").strip()

        category = ""
        classes = e.get("classifications", []) if isinstance(e.get("classifications"), list) else []
        if classes and isinstance(classes[0], dict):
            seg = classes[0].get("segment", {})
            if isinstance(seg, dict):
                category = str(seg.get("name") or "").strip()

        out.append(
            LocalEvent(
                name=name,
                date=date,
                time=time,
                venue=venue_name,
                city=city,
                category=category,
                url=str(e.get("url") or "").strip(),
                is_tonight=bool(today and date == today),
            )
        )
    return out


def fetch_events(
    lat: float,
    lon: float,
    *,
    radius_miles: int = 30,
    days_ahead: int = 7,
    size: int = 20,
    key: str | None = None,
    timeout: float = 15.0,
) -> list[LocalEvent]:
    """Fetch upcoming events near a coordinate. Never raises.

    Returns ``[]`` when no key is configured or the request/parse fails, so the
    nightly run degrades cleanly.
    """
    k = key if key is not None else api_key()
    if not k:
        return []
    now = datetime.datetime.now(datetime.timezone.utc)
    params = {
        "apikey": k,
        "latlong": f"{lat},{lon}",
        "radius": str(max(1, int(radius_miles))),
        "unit": "miles",
        "startDateTime": _utc_z(now),
        "endDateTime": _utc_z(now + datetime.timedelta(days=max(1, days_ahead))),
        "sort": "date,asc",
        "size": str(max(1, min(int(size), 200))),
    }
    url = f"{_ENDPOINT}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - trusted Ticketmaster endpoint
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, ValueError, TimeoutError, OSError):
        return []
    today = datetime.date.today().isoformat()
    return parse_events(payload, today=today)


def _fmt(e: LocalEvent) -> str:
    where = f" at {e.venue}" if e.venue else ""
    city = f", {e.city}" if e.city else ""
    when = e.date + (f" {e.time}" if e.time else "")
    cat = f" [{e.category}]" if e.category else ""
    return f"{when} — {e.name}{where}{city}{cat}"


def render_events(events: list[LocalEvent], *, city_hint: str = "Minot") -> str:
    """A deterministic readout of nearby events for the brief."""
    if not events:
        return (
            f"No major ticketed events near {city_hint} in the window "
            "(quiet stretch — you're the destination tonight)."
        )
    tonight = [e for e in events if e.is_tonight]
    upcoming = [e for e in events if not e.is_tonight]
    lines: list[str] = []
    if tonight:
        lines.append("**Tonight nearby:**")
        lines += [f"- {_fmt(e)}" for e in tonight]
        lines.append(
            "- ⤷ Ride the spillover: crowds are downtown — be the after/before stop."
        )
    if upcoming:
        lines.append("**Coming up nearby:**")
        lines += [f"- {_fmt(e)}" for e in upcoming[:6]]
    return "\n".join(lines)
