"""
Nearby-venue search — turn a category into real, named Minot businesses with
contact details, using the Google Places API (New).

For the bar agent this powers the v2 "recruit nearby Main Street venues onto
DrinkMinot" density play (find the bars/lounges next door, then help claim
them). It is NOT wired into the nightly run yet; it's here so v2 doesn't need a
rewrite.

Enabled by ``DOWNUNDER_SEARCH_API_KEY`` (see ``config.py``). With no key it
degrades gracefully: ``search_configured()`` is False and
``search_local_businesses()`` returns ``[]`` instead of raising.

Deliberately dependency-free (stdlib ``urllib`` only).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import load_config

_PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
# Ask only for the fields we use, to keep the response small and the call cheap.
_FIELD_MASK = ",".join(
    [
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.websiteUri",
    ]
)
_USER_AGENT = "DownunderAgent/0.1 (+https://drinkminot.com)"


@dataclass
class PlaceLead:
    """One real business returned by the search provider."""

    name: str
    address: str = ""
    phone: str = ""
    website: str = ""
    source: str = "Google Places"


def search_configured(api_key: str | None = None) -> bool:
    """True when a search key is available (real results vs none)."""
    key = api_key if api_key is not None else load_config().search_api_key
    return bool(key)


def build_search_text(category: str, location: str = "Minot, ND") -> str:
    """Compose a Places text query from a category + location. Pure."""
    category = (category or "").strip()
    location = (location or "").strip() or "Minot, ND"
    if not category:
        return location
    return f"{category} in {location}"


def parse_places(payload: dict) -> list[PlaceLead]:
    """Parse a Places ``searchText`` response into ``PlaceLead`` rows. Pure."""
    out: list[PlaceLead] = []
    if not isinstance(payload, dict):
        return out
    for place in payload.get("places", []) or []:
        if not isinstance(place, dict):
            continue
        name = ""
        display = place.get("displayName")
        if isinstance(display, dict):
            name = (display.get("text") or "").strip()
        elif isinstance(display, str):
            name = display.strip()
        if not name:
            continue
        out.append(
            PlaceLead(
                name=name,
                address=(place.get("formattedAddress") or "").strip(),
                phone=(place.get("nationalPhoneNumber") or "").strip(),
                website=(place.get("websiteUri") or "").strip(),
            )
        )
    return out


def search_local_businesses(
    category: str,
    location: str = "Minot, ND",
    *,
    api_key: str | None = None,
    limit: int = 5,
    timeout: float = 15.0,
) -> list[PlaceLead]:
    """Find real local businesses matching a category.

    Returns ``[]`` (never raises) when no key is configured or the request
    fails, so callers can degrade without special-casing.
    """
    key = api_key if api_key is not None else load_config().search_api_key
    if not key:
        return []
    limit = max(1, min(int(limit), 20))
    body = json.dumps(
        {"textQuery": build_search_text(category, location), "maxResultCount": limit}
    ).encode("utf-8")
    req = Request(
        _PLACES_SEARCH_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": _FIELD_MASK,
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - trusted Google endpoint
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, ValueError, TimeoutError, OSError):
        return []
    return parse_places(payload)[:limit]
