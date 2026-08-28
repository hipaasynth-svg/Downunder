"""Tests for the deterministic content scaffolding (no LLM required)."""

from __future__ import annotations

from datetime import date

from agents import content
from agents.models import NightAngle


def _angle():
    return NightAngle(id="etabs-ndad", title="E-tabs for a good cause")


def test_default_hashtags_are_local_and_capped():
    tags = content.default_hashtags(_angle(), "instagram")
    assert "#minotnd" in tags
    assert "#downunderminot" in tags
    assert len(tags) <= 12
    assert all(t.startswith("#") for t in tags)


def test_posting_schedule_spreads_and_rotates_platforms():
    slots = content.posting_schedule(date(2026, 8, 24), days=14, per_week=3)
    assert slots
    platforms = {p for _, p in slots}
    assert platforms <= set(content.PLATFORMS)
    # First slot is the start date.
    assert slots[0][0] == date(2026, 8, 24)


def test_blank_plan_fills_format_and_hashtags():
    posts = content.blank_plan_for_angle(_angle(), date(2026, 8, 24), days=7, per_week=3)
    assert posts
    for p in posts:
        assert p.related_angle_id == "etabs-ndad"
        assert p.format in {"post", "reel", "short", "story"}
        assert p.hashtags  # scaffolded


def test_render_plan_markdown():
    posts = content.blank_plan_for_angle(_angle(), date(2026, 8, 24), days=7, per_week=2)
    md = content.render_plan("E-tabs for a good cause", posts)
    assert md.startswith("# Content plan: E-tabs for a good cause")
    assert "post(s)" in md
