"""Tests for the data models (pydantic only, no nooa / LLM)."""

from __future__ import annotations

from agents.models import (
    AgentState,
    BusynessEntry,
    Character,
    ComicPanel,
    ComicStrip,
    NightAngle,
    VenuePulse,
)


def test_venue_pulse_tag_url():
    pulse = VenuePulse(id=63, ok=True)
    assert pulse.tag_url("https://drinkminot.com") == "https://drinkminot.com/?r=63"
    assert pulse.tag_url("https://drinkminot.com/") == "https://drinkminot.com/?r=63"


def test_busyness_entry_is_logged():
    assert BusynessEntry(date="2026-08-28", score=3).is_logged()
    assert not BusynessEntry(date="2026-08-28", score=0).is_logged()
    assert not BusynessEntry(date="2026-08-28", score=6).is_logged()


def test_agent_state_roundtrip():
    state = AgentState(
        venue_pulse=VenuePulse(id=63, ok=True, rating=4.1),
        angles=[NightAngle(id="a", title="A")],
        busyness_log=[BusynessEntry(date="2026-08-28", score=4)],
    )
    dumped = state.model_dump_json()
    back = AgentState.model_validate_json(dumped)
    assert back.venue_pulse.rating == 4.1
    assert back.angles[0].id == "a"
    assert back.busyness_log[0].score == 4


def test_night_angle_defaults_promotable():
    assert NightAngle(id="x", title="X").for_promo is True


def test_character_defaults_no_reference():
    ch = Character(id="marge", name="Marge")
    assert ch.reference_path == ""  # no canon art rendered yet


def test_agent_state_persists_cast_and_strip_fields():
    state = AgentState(
        cast=[Character(id="marge", name="Marge", look="grey bob", reference_path="cast/marge.png")],
    )
    back = AgentState.model_validate_json(state.model_dump_json())
    assert back.cast[0].name == "Marge"
    assert back.cast[0].reference_path == "cast/marge.png"


def test_comic_strip_roundtrip():
    strip = ComicStrip(
        id="s1", title="Payday", characters=["marge"],
        panels=[ComicPanel(scene="bar", speaker="marge", line="It's 4pm.")],
        caption="Come by.",
    )
    back = ComicStrip.model_validate_json(strip.model_dump_json())
    assert back.panels[0].line == "It's 4pm."
    assert back.characters == ["marge"]
