"""Tests for the Ticketmaster events parsing/rendering (no network)."""

from __future__ import annotations

from agents import events


def _payload():
    return {
        "_embedded": {
            "events": [
                {
                    "name": "Minotauros vs. Rivals",
                    "url": "https://tm/e/1",
                    "dates": {"start": {"localDate": "2026-08-28", "localTime": "19:05:00"}},
                    "classifications": [{"segment": {"name": "Sports"}}],
                    "_embedded": {"venues": [{"name": "Maysa Arena", "city": {"name": "Minot"}}]},
                },
                {
                    "name": "Country Night",
                    "url": "https://tm/e/2",
                    "dates": {"start": {"localDate": "2026-08-30"}},
                    "classifications": [{"segment": {"name": "Music"}}],
                    "_embedded": {"venues": [{"name": "Muni Auditorium", "city": {"name": "Minot"}}]},
                },
                {"name": "", "dates": {"start": {"localDate": "2026-08-31"}}},  # skipped: no name
            ]
        }
    }


def test_configured_reads_env(monkeypatch):
    monkeypatch.delenv("TICKETMASTER_API_KEY", raising=False)
    assert events.configured() is False
    monkeypatch.setenv("TICKETMASTER_API_KEY", "k")
    assert events.configured() is True


def test_parse_events_maps_fields_and_flags_tonight():
    evs = events.parse_events(_payload(), today="2026-08-28")
    assert len(evs) == 2  # the nameless one is skipped
    a = evs[0]
    assert a.name == "Minotauros vs. Rivals"
    assert a.date == "2026-08-28"
    assert a.time == "19:05"
    assert a.venue == "Maysa Arena"
    assert a.city == "Minot"
    assert a.category == "Sports"
    assert a.is_tonight is True
    assert evs[1].is_tonight is False


def test_parse_events_resilient_to_junk():
    assert events.parse_events({}, today="2026-08-28") == []
    assert events.parse_events("nope", today="2026-08-28") == []


def test_render_events_tonight_and_upcoming():
    evs = events.parse_events(_payload(), today="2026-08-28")
    text = events.render_events(evs)
    assert "Tonight nearby:" in text
    assert "Minotauros vs. Rivals" in text
    assert "Ride the spillover" in text
    assert "Coming up nearby:" in text
    assert "Country Night" in text


def test_render_events_empty():
    assert "No major ticketed events" in events.render_events([])


def test_fetch_events_returns_empty_without_key(monkeypatch):
    monkeypatch.delenv("TICKETMASTER_API_KEY", raising=False)
    assert events.fetch_events(48.23, -101.29) == []
