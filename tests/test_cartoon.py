"""Tests for the pure cartoon logic (no LLM / network required)."""

from __future__ import annotations

from agents import cartoon
from agents.models import Character, ComicPanel, ComicStrip


def _cast():
    return [
        Character(id="marge", name="Marge", role="bartender", look="tall woman, grey bob, flannel", personality="deadpan"),
        Character(id="lucky", name="Lucky", role="regular", look="stocky man, ND State cap, red beard"),
    ]


def _strip():
    return ComicStrip(
        id="s1",
        title="Payday Friday",
        angle_id="weekend-downtown",
        characters=["marge", "lucky"],
        panels=[
            ComicPanel(scene="Lucky drops a paycheck on the bar", speaker="lucky", line="Big night, Marge."),
            ComicPanel(scene="Marge slides a soda over", speaker="marge", line="It's 4pm."),
        ],
        caption="Start the weekend downtown.",
    )


def test_character_by_id_matches_id_or_name():
    cast = _cast()
    assert cartoon.character_by_id(cast, "marge").name == "Marge"
    assert cartoon.character_by_id(cast, "Lucky").id == "lucky"
    assert cartoon.character_by_id(cast, "nobody") is None


def test_character_reference_prompt_includes_look_and_guardrails():
    p = cartoon.character_reference_prompt(_cast()[0])
    assert "Marge" in p
    assert "grey bob" in p  # the look carries through for consistency
    assert "plain" in p.lower()  # plain background character sheet
    assert "21+" in p  # responsible-alcohol guardrail baked in


def test_strip_image_prompt_lays_out_panels_and_dialogue():
    p = cartoon.strip_image_prompt(_strip(), _cast())
    assert "2-panel comic strip" in p
    assert "Marge" in p and "Lucky" in p
    assert "Panel 1:" in p and "Panel 2:" in p
    assert '"Big night, Marge."' in p
    assert "reference image" in p.lower()  # consistency instruction
    assert "21+" in p


def test_strip_image_prompt_handles_unknown_characters():
    strip = ComicStrip(id="s", title="T", characters=["ghost"], panels=[ComicPanel(scene="empty bar")])
    # Should not raise even when a featured id isn't in the cast.
    p = cartoon.strip_image_prompt(strip, _cast())
    assert "1-panel comic strip" in p


def test_render_strip_markdown():
    md = cartoon.render_strip_markdown(_strip(), _cast())
    assert md.startswith("# Payday Friday")
    assert "Marge" in md and "Lucky" in md
    assert "Panel 1." in md and "Panel 2." in md
    assert "Big night, Marge." in md
    assert "**Caption:** Start the weekend downtown." in md
