"""Tests for env-driven configuration."""

from __future__ import annotations

from agents.config import load_config


def test_defaults_point_at_down_under():
    cfg = load_config()
    assert cfg.bar_name == "Down Under"
    assert cfg.venue_id == 63
    assert cfg.drink_url == "https://drinkminot.com"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("DOWNUNDER_BAR_NAME", "Some Other Bar")
    monkeypatch.setenv("DOWNUNDER_VENUE_ID", "12")
    monkeypatch.setenv("DOWNUNDER_DRINK_URL", "https://example.test")
    cfg = load_config()
    assert cfg.bar_name == "Some Other Bar"
    assert cfg.venue_id == 12
    assert cfg.drink_url == "https://example.test"
