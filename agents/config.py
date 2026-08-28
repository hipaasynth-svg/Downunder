"""
Configuration for the Down Under, sourced from environment variables.

Every value has a default that preserves the project's current behaviour, so
nothing here is required to run locally. Override any of them via the
environment (see ``.env.example``) to point at a different bar, DrinkMinot
venue, or model without editing code.

A local ``.env`` file at the project root is loaded automatically on import
(via python-dotenv), so keys like ANTHROPIC_API_KEY just work without any
manual ``export``. Real environment variables always win over ``.env``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Default LLM used for creative / marketing / agentic work.
DEFAULT_MODEL = "claude-opus-4-8"


def load_env(path: str | None = None) -> bool:
    """Load a ``.env`` file into the process environment.

    Uses python-dotenv if installed; a no-op (returns False) if it isn't, so the
    package still works without the dependency. Existing real environment
    variables are never overridden. With no ``path``, searches upward from the
    current directory for a ``.env``. Returns True if a file was loaded.
    """
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        return False
    dotenv_path = path or find_dotenv(usecwd=True)
    if not dotenv_path:
        return False
    return load_dotenv(dotenv_path, override=False)


# Auto-load .env on import so a project-root .env "just works".
load_env()


@dataclass(frozen=True)
class Config:
    # LLM
    model: str = DEFAULT_MODEL

    # The bar this agent works for.
    bar_name: str = "Down Under"
    bar_city: str = "Minot, ND"

    # DrinkMinot loyalty platform (the customer-facing funnel).
    #   drink_url    — public site the agent reads (GET /api/state).
    #   venue_id     — Down Under's frozen venue id in DrinkMinot's seed (id 63).
    #   A shopper taps the in-store tag at ``<drink_url>/?r=<venue_id>``.
    drink_url: str = "https://drinkminot.com"
    venue_id: int = 63

    # Repo ownership (any site changes ship only via PR).
    github_owner: str = "hipaasynth-svg"
    github_repo: str = "drinkminot"
    default_branch: str = "main"

    # Local state persistence
    state_path: str = "downunder_state.json"

    # Nearby-venue search / enrichment (Google Places). Empty = no real search
    # wired; the v2 "recruit nearby venues onto DrinkMinot" scan stays off.
    search_api_key: str = ""


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def load_config() -> Config:
    """Build a Config, letting DOWNUNDER_* env vars override the defaults."""
    d = Config()
    return Config(
        model=_env("DOWNUNDER_MODEL", d.model),
        bar_name=_env("DOWNUNDER_BAR_NAME", d.bar_name),
        bar_city=_env("DOWNUNDER_BAR_CITY", d.bar_city),
        drink_url=_env("DOWNUNDER_DRINK_URL", d.drink_url),
        venue_id=int(_env("DOWNUNDER_VENUE_ID", str(d.venue_id)) or d.venue_id),
        github_owner=_env("DOWNUNDER_GITHUB_OWNER", d.github_owner),
        github_repo=_env("DOWNUNDER_GITHUB_REPO", d.github_repo),
        default_branch=_env("DOWNUNDER_DEFAULT_BRANCH", d.default_branch),
        state_path=_env("DOWNUNDER_STATE_PATH", d.state_path),
        search_api_key=_env("DOWNUNDER_SEARCH_API_KEY", d.search_api_key),
    )
