"""
Local event intelligence from PredictHQ (https://api.predicthq.com/v1/events/).

PredictHQ is the purpose-built "predict big nights" source: concerts, sports,
festivals, community events, plus predicted attendance and a local rank — far
richer than a ticketing feed. Paid, but with a Free tier that covers one
low-volume nightly query for a single bar.

The agent uses this to AUTO-POPULATE the curated Minot events feed: it fetches
upcoming events near the bar and hands them to ``local_events.sync_events`` which
upserts them into DrinkMinot's ``/api/events`` under source ``predicthq`` (so a
re-run never duplicates and never touches hand-curated events).

Enabled by ``PREDICTHQ_TOKEN`` (create an Events-scoped token in the PredictHQ
control panel). With no token: ``configured()`` is False and ``fetch_events()``
returns ``[]`` — the sync simply doesn't run. Dependency-free (stdlib ``urllib``).

API: GET /v1/events/  (Bearer token)
  params: within=<radius>mi@<lat>,<lon>, active.gte, active.lte, category,
          sort=start, limit
  results[]: { id, title, category, start (ISO), entities:[{name,type}],
               rank, local_rank, phq_attendance, ... }
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

_ENDPOINT = "https://api.predicthq.com/v1/events/"
# Categories worth a bar's attention (crowds downtown). PredictHQ category slugs.
DEFAULT_CATEGORIES = (
    "concerts,performing-arts,sports,festivals,community,expos,conferences"
)
SOURCE = "predicthq"


def token() -> str:
    return os.environ.get("PREDICTHQ_TOKEN", "").strip()


def configured() -> bool:
    """True when a PredictHQ Events token is available."""
    return bool(token())


def _venue_of(entities: Any) -> str:
    if not isinstance(entities, list):
        return ""
    for ent in entities:
        if isinstance(ent, dict) and ent.get("type") == "venue" and ent.get("name"):
            return str(ent["name"]).strip()
    # fall back to the first named entity
    for ent in entities:
        if isinstance(ent, dict) and ent.get("name"):
            return str(ent["name"]).strip()
    return ""


def parse_events(payload: dict[str, Any], *, today: str = "") -> list[LocalEvent]:
    """Parse a PredictHQ ``/v1/events/`` response into LocalEvent rows. Pure.

    Keeps the PredictHQ id as ``source_id`` for idempotent syncing. Malformed
    entries are skipped rather than raising.
    """
    out: list[LocalEvent] = []
    if not isinstance(payload, dict):
        return out
    for e in payload.get("results", []) or []:
        if not isinstance(e, dict):
            continue
        name = str(e.get("title") or "").strip()
        if not name:
            continue
        start = str(e.get("start") or "").strip()
        date = start[:10]
        time = start[11:16] if "T" in start else ""
        out.append(
            LocalEvent(
                name=name,
                date=date,
                time=time,
                venue=_venue_of(e.get("entities")),
                category=str(e.get("category") or "").strip(),
                url="",
                is_tonight=bool(today and date == today),
                source=SOURCE,
                source_id=str(e.get("id") or "").strip(),
            )
        )
    return out


def fetch_events(
    lat: float,
    lon: float,
    *,
    radius_miles: int = 30,
    days_ahead: int = 14,
    limit: int = 50,
    api_token: str | None = None,
    timeout: float = 15.0,
) -> list[LocalEvent]:
    """Fetch upcoming events near a coordinate from PredictHQ. Never raises.

    Returns ``[]`` when no token is set or the request/parse fails.
    """
    tok = api_token if api_token is not None else token()
    if not tok:
        return []
    today = datetime.date.today()
    params = {
        "within": f"{max(1, int(radius_miles))}mi@{lat},{lon}",
        "active.gte": today.isoformat(),
        "active.lte": (today + datetime.timedelta(days=max(1, days_ahead))).isoformat(),
        "category": DEFAULT_CATEGORIES,
        "sort": "start",
        "limit": str(max(1, min(int(limit), 100))),
    }
    url = f"{_ENDPOINT}?{urlencode(params)}"
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - trusted PredictHQ endpoint
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, ValueError, TimeoutError, OSError):
        return []
    return parse_events(payload, today=today.isoformat())
