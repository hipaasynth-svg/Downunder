"""Tests for the data models (pydantic only, no nooa / LLM)."""

from __future__ import annotations

from agents.models import AgentState, BusynessEntry, NightAngle, VenuePulse


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
