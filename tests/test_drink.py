"""Tests for the DrinkMinot reader (network mocked)."""

from __future__ import annotations

from agents import drink


def test_fetch_pulse_maps_from_state(monkeypatch):
    payload = {
        "persistent": True,
        "restaurants": [
            {"id": 63, "name": "Down Under Bar", "rating": 4.2, "ratingCount": 5,
             "upvotes": 4, "totalRatings": 7, "reward": "Free item", "claimed": True},
        ],
    }
    monkeypatch.setattr(drink, "fetch_state", lambda url, timeout=15.0: payload)
    pulse = drink.fetch_pulse("https://drinkminot.com", 63)
    assert pulse.ok
    assert pulse.name == "Down Under Bar"
    assert pulse.rating == 4.2
    assert pulse.claimed is True


def test_fetch_pulse_propagates_fetch_error(monkeypatch):
    monkeypatch.setattr(
        drink, "fetch_state", lambda url, timeout=15.0: {"ok": False, "error": "URLError: down"}
    )
    pulse = drink.fetch_pulse("https://drinkminot.com", 63)
    assert not pulse.ok
    assert "down" in pulse.error


def test_fetch_state_bad_url_is_resilient():
    # No network / bad host must not raise — it returns an error object.
    out = drink.fetch_state("http://127.0.0.1:0", timeout=0.01)
    assert isinstance(out, dict)
    assert out.get("ok") is False
    assert "error" in out
