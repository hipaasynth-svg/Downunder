"""
Pure, deterministic cartoon logic — no LLM, no network, no nooa.

The creative work (inventing the cast, writing a strip's panels + dialogue) is
done by the LLM in ``agents/comic_agent.py``. The actual image rendering is done
by ``agents/gemini.py``. Everything here is pure and unit-testable: it builds the
image prompts (so character look + house style stay consistent), resolves who
speaks in a panel, and renders a text storyboard for the no-key / degraded path.

Character consistency approach (the field-standard technique): give each
character ONE locked "canon" reference image, then feed that image into every
future strip. These helpers assemble the prompts around that; the reference
bytes themselves are passed to the image model by the caller.
"""

from __future__ import annotations

from .models import Character, ComicStrip

# The house look for every Down Under cartoon. Edit here to restyle everything.
DEFAULT_STYLE = (
    "warm, friendly hand-drawn cartoon style; bold clean outlines, flat cel "
    "shading, cozy dim-bar lighting with neon accents; a downtown small-town "
    "North Dakota bar setting; wholesome and good-humored, never edgy"
)

# Baked into every prompt so nothing the model draws breaks the rules.
_GUARDRAILS = (
    "All characters are clearly adults (21+). Do not depict minors. Keep it "
    "good-natured and responsible — no drunkenness, no glorifying heavy "
    "drinking, no one visibly intoxicated. This is about the place and the "
    "night, not volume drinking."
)


def character_by_id(cast: list[Character], cid: str) -> Character | None:
    for c in cast:
        if c.id == cid or c.name == cid:
            return c
    return None


def character_reference_prompt(char: Character, *, style: str = DEFAULT_STYLE) -> str:
    """Prompt to generate a character's locked CANON reference image (once).

    A clean character sheet on a plain background: the single source of truth the
    image model is handed on every future strip so the character stays on-model.
    """
    bits = [
        f"Character reference sheet for a recurring cartoon character named "
        f"{char.name}.",
        f"Style: {style}.",
    ]
    if char.role:
        bits.append(f"Role: {char.role} at the Down Under, a downtown Minot, ND bar.")
    if char.look:
        bits.append(f"Appearance (keep exactly consistent): {char.look}.")
    if char.personality:
        bits.append(f"Personality to convey: {char.personality}.")
    bits.append(
        "Full body, front view, neutral friendly pose, on a plain flat "
        "background, no text, no speech bubbles. This is the canonical look to "
        "reuse in every future strip."
    )
    bits.append(_GUARDRAILS)
    return " ".join(bits)


def _speaker_name(cast: list[Character], speaker: str) -> str:
    c = character_by_id(cast, speaker)
    return c.name if c else speaker


def strip_image_prompt(
    strip: ComicStrip, cast: list[Character], *, style: str = DEFAULT_STYLE
) -> str:
    """Prompt to render the whole strip as ONE multi-panel image.

    Names the featured characters (their canon reference images are attached by
    the caller for consistency) and lays out each panel's scene + spoken line.
    """
    featured = [character_by_id(cast, cid) for cid in strip.characters]
    featured = [c for c in featured if c is not None]
    names = ", ".join(c.name for c in featured) if featured else "the cast"

    n = max(1, len(strip.panels))
    lines = [
        f"A {n}-panel comic strip titled \"{strip.title}\", laid out left to "
        f"right in equal panels.",
        f"Style: {style}.",
        f"Featuring these recurring characters, drawn exactly like their "
        f"reference images: {names}.",
    ]
    for i, panel in enumerate(strip.panels, 1):
        who = _speaker_name(cast, panel.speaker) if panel.speaker else ""
        scene = panel.scene.strip() or "the bar"
        piece = f"Panel {i}: {scene}."
        if panel.line.strip():
            speaker_bit = f"{who} says" if who else "caption reads"
            piece += f' A speech bubble where {speaker_bit}: "{panel.line.strip()}".'
        lines.append(piece)
    lines.append(
        "Keep every character identical to their reference across all panels. "
        "Make any speech-bubble text short and clearly legible."
    )
    lines.append(_GUARDRAILS)
    return " ".join(lines)


def render_strip_markdown(strip: ComicStrip, cast: list[Character]) -> str:
    """The text storyboard — the graceful-degradation output when no image key
    is set, and the human-readable record of what the strip says."""
    out = [f"# {strip.title or 'Untitled strip'}"]
    if strip.characters:
        names = ", ".join(_speaker_name(cast, c) for c in strip.characters)
        out.append(f"_Cast: {names}_")
    out.append("")
    if not strip.panels:
        out.append("_No panels written._")
    for i, panel in enumerate(strip.panels, 1):
        out.append(f"**Panel {i}.** {panel.scene.strip()}")
        if panel.line.strip():
            who = _speaker_name(cast, panel.speaker) if panel.speaker else "Caption"
            out.append(f"> {who}: {panel.line.strip()}")
        out.append("")
    if strip.caption:
        out.append(f"**Caption:** {strip.caption}")
    return "\n".join(out).rstrip() + "\n"
