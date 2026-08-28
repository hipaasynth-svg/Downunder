"""
Read the live DrinkMinot loyalty platform so the agent works from what is
really there.

DrinkMinot exposes a public ``GET /api/state`` endpoint that returns every
venue's profile + vote counters (passwords stripped) and a ``persistent`` flag.
This module fetches it and turns one venue's row into a ``VenuePulse``.

Deliberately dependency-free (stdlib ``urllib`` only), matching the reader in
the sibling art-manager project, and resilient: a network or JSON failure
becomes an ``ok=False`` pulse rather than a raised exception.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import logic
from .models import VenuePulse

_USER_AGENT = "DownunderAgent/0.1 (+https://drinkminot.com)"


def fetch_state(drink_url: str, *, timeout: float = 15.0) -> dict[str, Any]:
    """Fetch the public ``GET /api/state`` JSON from DrinkMinot.

    Returns the payload unchanged (``{persistent, restaurants:[...]}``) so the
    caller can read the real venue rows. Network / invalid-JSON failures are
    represented in a small error object rather than raised.
    """
    api_url = f"{drink_url.rstrip('/')}/api/state"
    req = Request(api_url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - trusted DrinkMinot endpoint
            charset = resp.headers.get_content_charset() or "utf-8"
            payload = json.loads(resp.read().decode(charset, errors="replace"))
        if not isinstance(payload, dict):
            raise ValueError("state API response must be a JSON object")
        return payload
    except (HTTPError, URLError, ValueError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def fetch_pulse(drink_url: str, venue_id: int, *, timeout: float = 15.0) -> VenuePulse:
    """Read one venue's live loyalty state as a ``VenuePulse``.

    Combines ``fetch_state`` (network) with ``logic.parse_pulse`` (pure), so the
    parsing stays unit-testable without a network. Always returns a pulse; check
    ``pulse.ok``.
    """
    state = fetch_state(drink_url, timeout=timeout)
    return logic.parse_pulse(state, venue_id)
