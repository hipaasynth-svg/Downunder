"""Tests for the pure business logic (no nooa / LLM required)."""

from __future__ import annotations

import datetime

from agents import logic
from agents.models import BusynessEntry, NightAngle


# ---------- DrinkMinot pulse parsing ----------
def _state(persistent=True, **overrides):
    row = {
        "id": 63,
        "name": "Down Under Bar",
        "category": "Bars & Lounges",
        "address": "Minot, ND",
        "hours": "Mon-Thu 10am-10pm",
        "rating": 4.5,
        "ratingCount": 8,
        "upvotes": 6,
        "totalRatings": 10,
        "claimed": False,
        "paid": False,
        "reward": "Free item on your 10th punch",
        "couponValidDays": 14,
        "happyHour": {"enabled": True, "days": [4], "start": "15:00", "end": "18:00", "special": "$1 off"},
    }
    row.update(overrides)
    return {"persistent": persistent, "restaurants": [{"id": 1, "name": "Other"}, row]}


def test_parse_pulse_maps_fields():
    pulse = logic.parse_pulse(_state(), 63)
    assert pulse.ok
    assert pulse.id == 63
    assert pulse.name == "Down Under Bar"
    assert pulse.rating == 4.5
    assert pulse.rating_count == 8
    assert pulse.upvotes == 6
    assert pulse.total_ratings == 10
    assert pulse.reward.startswith("Free item")
    assert pulse.coupon_valid_days == 14
    assert pulse.persistent is True
    assert pulse.happy_hour["special"] == "$1 off"


def test_parse_pulse_reports_persistence_off():
    pulse = logic.parse_pulse(_state(persistent=False), 63)
    assert pulse.ok
    assert pulse.persistent is False


def test_parse_pulse_missing_venue():
    pulse = logic.parse_pulse({"persistent": True, "restaurants": [{"id": 1}]}, 63)
    assert not pulse.ok
    assert "not found" in pulse.error


def test_parse_pulse_bad_payload():
    assert not logic.parse_pulse({"ok": False, "error": "boom"}, 63).ok
    assert not logic.parse_pulse({}, 63).ok  # no restaurants
    assert not logic.parse_pulse("nope", 63).ok


def test_render_pulse_warns_when_not_persistent():
    text = logic.render_pulse(logic.parse_pulse(_state(persistent=False), 63), drink_url="https://drinkminot.com")
    assert "NOT attached" in text
    assert "/?r=63" in text


def test_render_pulse_flags_unclaimed():
    text = logic.render_pulse(logic.parse_pulse(_state(), 63))
    assert "UNCLAIMED" in text


def test_format_happy_hour():
    assert logic.format_happy_hour({"enabled": False}) == ""
    txt = logic.format_happy_hour({"enabled": True, "days": [5], "start": "15:00", "end": "18:00", "special": "$1 off"})
    assert "15:00-18:00" in txt and "$1 off" in txt


# ---------- rotation / tonight ----------
def _angle(aid, day="", promo=True):
    return NightAngle(id=aid, title=aid.title(), day=day, for_promo=promo)


def test_pick_tonight_prefers_weekday_specific():
    angles = [_angle("evergreen"), _angle("friday", day="Friday")]
    friday = datetime.date(2026, 8, 28)  # a Friday
    assert friday.weekday() == 4
    assert logic.pick_tonight(angles, date=friday).id == "friday"


def test_pick_tonight_rotates_when_no_weekday_match():
    angles = [_angle("a"), _angle("b")]
    monday = datetime.date(2026, 8, 24)
    pick = logic.pick_tonight(angles, date=monday)
    assert pick.id in {"a", "b"}


def test_pick_tonight_skips_non_promo():
    angles = [_angle("off", promo=False)]
    assert logic.pick_tonight(angles) is None


def test_rotate_daily_windows_and_wraps():
    items = ["a", "b", "c"]
    assert logic.rotate_daily(items, 1, 0) == ["a"]
    assert logic.rotate_daily(items, 1, 1) == ["b"]
    assert logic.rotate_daily([], 2, 3) == []


# ---------- busy-ness log ----------
def test_upsert_busyness_replaces_same_date_and_sorts():
    log: list[BusynessEntry] = []
    log = logic.upsert_busyness(log, BusynessEntry(date="2026-08-20", score=3))
    log = logic.upsert_busyness(log, BusynessEntry(date="2026-08-19", score=2))
    log = logic.upsert_busyness(log, BusynessEntry(date="2026-08-20", score=5))  # replace
    assert [e.date for e in log] == ["2026-08-19", "2026-08-20"]
    assert log[-1].score == 5


def test_busyness_rollup_average_and_best_weekday():
    log = [
        BusynessEntry(date="2026-08-21", score=5),  # Friday
        BusynessEntry(date="2026-08-28", score=3),  # Friday
        BusynessEntry(date="2026-08-24", score=1),  # Monday
        BusynessEntry(date="2026-08-25", score=0),  # not logged, ignored
    ]
    roll = logic.busyness_rollup(log)
    assert roll.nights_logged == 3
    assert roll.average == round((5 + 3 + 1) / 3, 2)
    assert roll.best_weekday == "Friday"
    assert roll.best_weekday_average == 4.0
    assert roll.last_date == "2026-08-28"


def test_busyness_rollup_empty():
    assert logic.busyness_rollup([]).nights_logged == 0


def test_busyness_prompt_includes_context():
    roll = logic.busyness_rollup([BusynessEntry(date="2026-08-28", score=4)])
    prompt = logic.busyness_prompt(roll, date="2026-08-29")
    assert "1 (dead) to 5 (packed)" in prompt
    assert "1 night(s) logged" in prompt


# ---------- seed angles ----------
def test_default_angles_carry_loyalty_url_and_are_promotable():
    angles = logic.default_angles("https://drinkminot.com/?r=63")
    assert angles
    assert all(a.for_promo for a in angles)
    assert any("?r=63" in a.loyalty_url for a in angles)
    # A Friday-specific angle exists so weekend nights lead with it.
    assert any(a.day == "Friday" for a in angles)
