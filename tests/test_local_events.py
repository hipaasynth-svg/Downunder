"""Tests for the curated Minot events reader (no network)."""

from __future__ import annotations

from agents import local_events


def _payload():
    return {
        "ok": True,
        "events": [
            {"title": "NDSU Bison watch party", "date": "2026-08-28", "time": "18:00",
             "venue": "Down Under Bar", "category": "Sports", "url": "https://x"},
            {"title": "State Fair Concert", "date": "2026-08-30", "venue": "Fairgrounds"},
            {"date": "2026-08-31"},  # skipped: no title
        ],
    }


def test_parse_events_maps_title_to_name_and_flags_tonight():
    evs = local_events.parse_events(_payload(), today="2026-08-28")
    assert len(evs) == 2
    a = evs[0]
    assert a.name == "NDSU Bison watch party"
    assert a.date == "2026-08-28"
    assert a.time == "18:00"
    assert a.venue == "Down Under Bar"
    assert a.category == "Sports"
    assert a.is_tonight is True
    assert evs[1].is_tonight is False


def test_parse_events_resilient():
    assert local_events.parse_events({}, today="2026-08-28") == []
    assert local_events.parse_events("nope", today="2026-08-28") == []
    assert local_events.parse_events({"events": None}) == []


def test_render_events_tonight_and_upcoming():
    text = local_events.render_events(local_events.parse_events(_payload(), today="2026-08-28"))
    assert "In Minot tonight:" in text
    assert "NDSU Bison watch party" in text
    assert "Coming up in Minot:" in text
    assert "State Fair Concert" in text


def test_render_events_empty_points_to_admin():
    assert "/api/events" in local_events.render_events([])
