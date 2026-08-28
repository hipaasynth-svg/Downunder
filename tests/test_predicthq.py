"""Tests for the PredictHQ parsing + sync payload (no network)."""

from __future__ import annotations

from agents import local_events, predicthq
from agents.models import LocalEvent


def _payload():
    return {
        "count": 2,
        "results": [
            {
                "id": "abc123",
                "title": "Big Concert",
                "category": "concerts",
                "start": "2026-08-28T19:30:00Z",
                "entities": [{"name": "Maysa Arena", "type": "venue"}],
                "rank": 60,
                "local_rank": 80,
                "phq_attendance": 3000,
            },
            {
                "id": "def456",
                "title": "Street Festival",
                "category": "festivals",
                "start": "2026-08-30",
                "entities": [{"name": "Some Promoter", "type": "organization"}],
            },
            {"title": "", "start": "2026-09-01"},  # skipped: no title
        ],
    }


def test_configured_reads_env(monkeypatch):
    monkeypatch.delenv("PREDICTHQ_TOKEN", raising=False)
    assert predicthq.configured() is False
    monkeypatch.setenv("PREDICTHQ_TOKEN", "tok")
    assert predicthq.configured() is True


def test_parse_events_maps_fields_and_source():
    evs = predicthq.parse_events(_payload(), today="2026-08-28")
    assert len(evs) == 2
    a = evs[0]
    assert a.name == "Big Concert"
    assert a.date == "2026-08-28"
    assert a.time == "19:30"
    assert a.venue == "Maysa Arena"  # picks the venue entity
    assert a.category == "concerts"
    assert a.is_tonight is True
    assert a.source == "predicthq"
    assert a.source_id == "abc123"
    # festival: no venue-type entity -> falls back to first named entity
    assert evs[1].venue == "Some Promoter"
    assert evs[1].is_tonight is False


def test_parse_events_resilient():
    assert predicthq.parse_events({}, today="2026-08-28") == []
    assert predicthq.parse_events("nope", today="2026-08-28") == []


def test_fetch_events_returns_empty_without_token(monkeypatch):
    monkeypatch.delenv("PREDICTHQ_TOKEN", raising=False)
    assert predicthq.fetch_events(48.23, -101.29) == []


def test_event_to_record_uses_stable_id():
    e = LocalEvent(name="X", date="2026-09-01", source="predicthq", source_id="abc123")
    rec = local_events.event_to_record(e)
    assert rec["id"] == "predicthq_abc123"
    assert rec["title"] == "X"


def test_event_to_record_no_id_when_no_source():
    rec = local_events.event_to_record(LocalEvent(name="Y", date="2026-09-01"))
    assert "id" not in rec


def test_sync_events_guards_missing_inputs():
    assert local_events.sync_events("", "pw", "predicthq", [])["ok"] is False
    assert local_events.sync_events("https://x", "", "predicthq", [])["ok"] is False
