"""
Tonight's weather from the US National Weather Service (api.weather.gov).

Free, no API key, US-authoritative. Weather is one of the biggest predictors of
who goes out, so the nightly brief factors tonight's forecast in.

NWS is a two-step API:
  1. GET https://api.weather.gov/points/{lat},{lon}
       -> properties.forecast (the forecast URL) and
          properties.relativeLocation.properties.{city,state}
  2. GET {forecast URL}
       -> properties.periods[]  (name, isDaytime, temperature, temperatureUnit,
          probabilityOfPrecipitation.value, windSpeed, shortForecast,
          detailedForecast)
NWS requires a descriptive User-Agent header (it 403s without one).

The parsing (``tonight_from_periods``) is pure and unit-tested; the fetch is
resilient — any failure yields an ``ok=False`` TonightWeather so the brief just
carries on. Dependency-free (stdlib ``urllib``).
"""

from __future__ import annotations

import datetime
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import TonightWeather

_USER_AGENT = "DownunderAgent/0.1 (cody@drinkminot.com)"
# Words in the forecast that mean a tougher night for foot traffic.
_ROUGH_WORDS = (
    "snow", "blizzard", "ice", "icy", "freezing", "sleet", "storm",
    "thunderstorm", "wind chill", "cold", "flurries", "wintry",
)


def _get(url: str, timeout: float) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/geo+json"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - trusted US government endpoint
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def pick_tonight_period(periods: list[dict]) -> dict | None:
    """Choose the period most relevant to a bar's night.

    Prefer the first evening/tonight/night period (by name or a night period);
    fall back to the first period. Returns None for an empty list.
    """
    if not periods:
        return None
    for p in periods:
        name = str(p.get("name", "")).lower()
        if any(w in name for w in ("tonight", "evening", "night")):
            return p
    for p in periods:
        if p.get("isDaytime") is False:
            return p
    return periods[0]


def _is_rough(temp: int | None, unit: str, text: str) -> bool:
    t = text.lower()
    if any(w in t for w in _ROUGH_WORDS):
        return True
    # Bitter cold keeps people home even under clear skies.
    if temp is not None and unit.upper() == "F" and temp <= 10:
        return True
    return False


def tonight_from_periods(periods: list[dict], *, city: str = "") -> TonightWeather:
    """Build a TonightWeather from NWS forecast periods. Pure; no network."""
    p = pick_tonight_period(periods)
    if p is None:
        return TonightWeather(city=city, ok=False, error="no forecast periods")

    temp = p.get("temperature")
    temp = int(temp) if isinstance(temp, (int, float)) else None
    unit = str(p.get("temperatureUnit") or "F")
    pop = p.get("probabilityOfPrecipitation")
    precip = pop.get("value") if isinstance(pop, dict) else None
    precip = int(precip) if isinstance(precip, (int, float)) else None
    short = str(p.get("shortForecast") or "").strip()
    detailed = str(p.get("detailedForecast") or "").strip()
    wind = " ".join(
        s for s in [str(p.get("windDirection") or "").strip(), str(p.get("windSpeed") or "").strip()] if s
    ).strip()

    return TonightWeather(
        city=city,
        period=str(p.get("name") or "").strip(),
        temperature=temp,
        temp_unit=unit,
        short_forecast=short,
        detailed_forecast=detailed,
        precip_chance=precip,
        wind=wind,
        is_daytime=bool(p.get("isDaytime")),
        rough=_is_rough(temp, unit, f"{short} {detailed}"),
        fetched_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        ok=True,
    )


def fetch_tonight(lat: float, lon: float, *, timeout: float = 15.0) -> TonightWeather:
    """Fetch tonight's forecast for a coordinate. Never raises.

    Returns an ``ok=False`` TonightWeather (carrying ``error``) on any network,
    HTTP, or parse failure, so the nightly run degrades cleanly.
    """
    try:
        points = _get(f"https://api.weather.gov/points/{lat},{lon}", timeout)
        props = points.get("properties", {}) if isinstance(points, dict) else {}
        forecast_url = props.get("forecast")
        rel = props.get("relativeLocation", {}).get("properties", {}) if isinstance(props.get("relativeLocation"), dict) else {}
        city = ", ".join(s for s in [str(rel.get("city") or "").strip(), str(rel.get("state") or "").strip()] if s)
        if not forecast_url:
            return TonightWeather(city=city, ok=False, error="no forecast URL in points response")
        forecast = _get(forecast_url, timeout)
        periods = forecast.get("properties", {}).get("periods", []) if isinstance(forecast, dict) else []
        return tonight_from_periods(periods if isinstance(periods, list) else [], city=city)
    except (HTTPError, URLError, ValueError, TimeoutError, OSError, KeyError) as exc:
        return TonightWeather(ok=False, error=f"{type(exc).__name__}: {exc}")


def render_weather(w: TonightWeather) -> str:
    """A deterministic one/two-line readout for the brief."""
    if not w.ok:
        return f"Tonight's weather unavailable: {w.error}"
    where = f" in {w.city}" if w.city else ""
    temp = f"{w.temperature}°{w.temp_unit}" if w.temperature is not None else "—"
    bits = [f"{w.short_forecast or 'Forecast'}, {temp}"]
    if w.precip_chance:
        bits.append(f"{w.precip_chance}% precip")
    if w.wind:
        bits.append(f"wind {w.wind}")
    line = f"**{w.period or 'Tonight'}{where}:** " + " · ".join(bits)
    if w.rough:
        line += "\n- ⚠ Rough weather — expect a quieter, regulars-only night; lean on e-tabs and the warm room."
    return line
