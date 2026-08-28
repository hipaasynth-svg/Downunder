"""Tests for the weather parsing/rendering (pure; no network)."""

from __future__ import annotations

from agents import weather


def _periods():
    return [
        {"name": "This Afternoon", "isDaytime": True, "temperature": 38,
         "temperatureUnit": "F", "shortForecast": "Sunny",
         "probabilityOfPrecipitation": {"value": 0}, "windSpeed": "10 mph", "windDirection": "NW"},
        {"name": "Tonight", "isDaytime": False, "temperature": 22,
         "temperatureUnit": "F", "shortForecast": "Partly Cloudy",
         "detailedForecast": "Partly cloudy, low around 22.",
         "probabilityOfPrecipitation": {"value": 20}, "windSpeed": "5 mph", "windDirection": "N"},
    ]


def test_pick_tonight_prefers_evening_period():
    p = weather.pick_tonight_period(_periods())
    assert p["name"] == "Tonight"


def test_pick_tonight_empty():
    assert weather.pick_tonight_period([]) is None


def test_tonight_from_periods_maps_fields():
    w = weather.tonight_from_periods(_periods(), city="Minot, ND")
    assert w.ok
    assert w.city == "Minot, ND"
    assert w.period == "Tonight"
    assert w.temperature == 22
    assert w.short_forecast == "Partly Cloudy"
    assert w.precip_chance == 20
    assert w.wind == "N 5 mph"
    assert w.is_daytime is False


def test_rough_flag_on_snow():
    periods = [{"name": "Tonight", "isDaytime": False, "temperature": 15,
                "temperatureUnit": "F", "shortForecast": "Snow Likely",
                "probabilityOfPrecipitation": {"value": 80}}]
    w = weather.tonight_from_periods(periods, city="Minot, ND")
    assert w.rough is True


def test_rough_flag_on_bitter_cold_even_if_clear():
    periods = [{"name": "Tonight", "isDaytime": False, "temperature": 2,
                "temperatureUnit": "F", "shortForecast": "Clear"}]
    assert weather.tonight_from_periods(periods).rough is True


def test_not_rough_on_mild_clear_night():
    periods = [{"name": "Tonight", "isDaytime": False, "temperature": 55,
                "temperatureUnit": "F", "shortForecast": "Clear"}]
    assert weather.tonight_from_periods(periods).rough is False


def test_render_weather_ok_and_rough():
    w = weather.tonight_from_periods(
        [{"name": "Tonight", "isDaytime": False, "temperature": 18, "temperatureUnit": "F",
          "shortForecast": "Snow", "probabilityOfPrecipitation": {"value": 70}, "windSpeed": "15 mph", "windDirection": "N"}],
        city="Minot, ND",
    )
    text = weather.render_weather(w)
    assert "Tonight in Minot, ND" in text
    assert "18°F" in text
    assert "70% precip" in text
    assert "Rough weather" in text


def test_render_weather_unavailable():
    from agents.models import TonightWeather
    assert "unavailable" in weather.render_weather(TonightWeather(ok=False, error="boom"))
