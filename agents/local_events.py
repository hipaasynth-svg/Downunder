"""
Curated Minot events from DrinkMinot's own ``/api/events`` endpoint.

This is the local events feed we host ourselves (see the drinkminot repo), so
it's the most reliable, most local source — curated, not scraped. The agent
reads it to know what's happening in Minot on a given night; Ticketmaster
(``agents.events``) stays as the national/ticketed complement.

Reads ``GET <drink_url>/api/events`` → ``{ ok, events:[...] }`` (upcoming only,
soonest first). Reuses the ``LocalEvent`` model. Resilient: any failure yields
``[]`` so the brief carries on. Dependency-free (stdlib ``urllib``).
"""

from __future__ import annotations

import datetime
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import LocalEvent

_USER_AGENT = "DownunderAgent/0.1 (+https://drinkminot.com)"


def parse_events(payload: dict[str, Any], *, today: str = "") -> list[LocalEvent]:
    """Parse a ``/api/events`` response into LocalEvent rows. Pure.

    Maps the endpoint's ``title`` → ``name`` and flags events happening tonight.
    Malformed entries are skipped rather than raising.
    """
    out: list[LocalEvent] = []
    if not isinstance(payload, dict):
        return out
    for e in payload.get("events", []) or []:
        if not isinstance(e, dict):
            continue
        name = str(e.get("title") or e.get("name") or "").strip()
        if not name:
            continue
        date = str(e.get("date") or "").strip()
        out.append(
            LocalEvent(
                name=name,
                date=date,
                time=str(e.get("time") or "").strip()[:5],
                venue=str(e.get("venue") or "").strip(),
                city=str(e.get("city") or "").strip(),
                category=str(e.get("category") or "").strip(),
                url=str(e.get("url") or "").strip(),
                is_tonight=bool(today and date == today),
            )
        )
    return out


def fetch_events(drink_url: str, *, timeout: float = 15.0) -> list[LocalEvent]:
    """Fetch curated Minot events from DrinkMinot. Never raises.

    Returns ``[]`` on any network/HTTP/parse failure, so the nightly run
    degrades cleanly.
    """
    url = f"{drink_url.rstrip('/')}/api/events"
    req = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - our own DrinkMinot endpoint
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, ValueError, TimeoutError, OSError):
        return []
    today = datetime.date.today().isoformat()
    return parse_events(payload, today=today)


def _fmt(e: LocalEvent) -> str:
    where = f" at {e.venue}" if e.venue else ""
    when = e.date + (f" {e.time}" if e.time else "")
    cat = f" [{e.category}]" if e.category else ""
    return f"{when} — {e.name}{where}{cat}"


def render_events(events: list[LocalEvent]) -> str:
    """A deterministic readout of curated Minot events for the brief."""
    if not events:
        return (
            "No curated Minot events listed yet — add them via DrinkMinot admin "
            "(/api/events) so the agent can plan around them."
        )
    tonight = [e for e in events if e.is_tonight]
    upcoming = [e for e in events if not e.is_tonight]
    lines: list[str] = []
    if tonight:
        lines.append("**In Minot tonight:**")
        lines += [f"- {_fmt(e)}" for e in tonight]
    if upcoming:
        lines.append("**Coming up in Minot:**")
        lines += [f"- {_fmt(e)}" for e in upcoming[:6]]
    return "\n".join(lines)
