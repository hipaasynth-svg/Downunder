"""
Nightly runner for the Down Under — the "floor" for the Down Under.

Loads state, reads the live DrinkMinot loyalty pulse, then produces one packet
Cody can act on in minutes:

  1. DrinkMinot loyalty pulse (deterministic, honest numbers)
  2. A ruthless nightly command board
  3. Tonight's angle + a short floor plan
  4. A CONTENT pack (Instagram caption + TikTok script) for tonight's angle
  5. A busy-ness log prompt (rate tonight 1-5 at close)

Every step is isolated so one failure doesn't abort the rest. Output prints to
the log and — via the GitHub Actions workflow — is emailed to Cody.

Nothing auto-publishes and nothing sends outreach: the only email is Cody's own
brief to himself.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Awaitable, Callable, TypeVar

from agents.downunder import DownunderAgent

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("downunder")

T = TypeVar("T")


async def _step(title: str, coro_factory: Callable[[], Awaitable[T]]) -> T | None:
    """Run one workflow step, printing the result and swallowing failures."""
    print(f"\n=== {title} ===")
    try:
        result = await coro_factory()
        print(result)
        return result
    except Exception as exc:  # noqa: BLE001 - runner should be resilient
        log.exception("step %r failed: %s", title, exc)
        print(f"[skipped: {exc}]")
        return None


async def _cartoons(agent, angle, today: str) -> None:
    """Cast + tonight's cartoon strip.

    Invents the recurring cast once (and remembers it), locks a canon reference
    image per character the first time (the consistency trick), writes tonight's
    strip, and renders it as one multi-panel image — or, with no GEMINI_API_KEY,
    prints the text storyboard so the feature still ships.
    """
    from pathlib import Path

    from agents import cartoon, gemini
    from agents.comic_agent import ComicAgent

    print("\n=== CARTOON ===")
    comic = ComicAgent()

    # 1. Ensure a recurring cast exists (invent once; persisted in state).
    if not agent.cast:
        agent.cast = await comic.invent_cast() or []
        if agent.cast:
            print(f"[invented cast: {', '.join(c.name for c in agent.cast)}]")
    if not agent.cast:
        print("[no cast yet — skipping cartoon]")
        return

    have_images = gemini.configured()
    if not have_images:
        print("[no GEMINI_API_KEY — text storyboard only; add the key to render images]")

    # 2. Lock a canon reference image per character, once (needs image gen).
    if have_images:
        cast_dir = Path("cast")
        cast_dir.mkdir(exist_ok=True)
        for ch in agent.cast:
            if ch.reference_path and Path(ch.reference_path).exists():
                continue
            png = gemini.generate_image(comic.character_reference_prompt(ch))
            if png:
                ref = cast_dir / f"{ch.id}.png"
                ref.write_bytes(png)
                ch.reference_path = str(ref)
                print(f"[locked canon art for {ch.name} -> {ref}]")
            else:
                print(f"[could not render canon art for {ch.name}]")

    # 3. Write tonight's strip.
    strip = await comic.write_strip(angle, agent.cast)
    if strip is None:
        print("[no strip written]")
        return

    # 4. Always show the storyboard (the human-readable record + no-key output).
    print(cartoon.render_strip_markdown(strip, agent.cast))

    # 5. Render one multi-panel image, feeding the cast's canon references.
    if have_images:
        refs: list[bytes] = []
        for cid in strip.characters:
            ch = cartoon.character_by_id(agent.cast, cid)
            if ch and ch.reference_path and Path(ch.reference_path).exists():
                refs.append(Path(ch.reference_path).read_bytes())
        png = gemini.generate_image(comic.strip_image_prompt(strip, agent.cast), refs)
        if png:
            out = Path(f"strip_{today}.png")
            out.write_bytes(png)
            strip.image_path = str(out)
            print(f"[rendered strip -> {out}]")
        else:
            print("[strip image render failed — storyboard above stands]")


async def main() -> None:
    agent = DownunderAgent()
    agent.load()

    today = datetime.date.today().isoformat()

    # ---- 1. Live DrinkMinot loyalty pulse (deterministic) ----
    print(f"\n=== DrinkMinot pulse: {agent.bar_name} (venue {agent.venue_id}) ===")
    try:
        pulse = agent.refresh_pulse()
        print(agent.pulse_readout(pulse))
    except Exception as exc:  # noqa: BLE001
        log.exception("pulse read failed: %s", exc)
        print(f"[pulse read skipped: {exc}]")

    # ---- 1b. Tonight's weather (api.weather.gov — free, no key) ----
    print("\n=== Tonight's weather ===")
    try:
        w = agent.refresh_weather()
        print(agent.weather_readout(w))
    except Exception as exc:  # noqa: BLE001
        log.exception("weather read failed: %s", exc)
        print(f"[weather read skipped: {exc}]")

    # ---- 1c. Curated Minot events (our own DrinkMinot /api/events) ----
    # First auto-populate from PredictHQ (when configured), then read the feed
    # back so tonight's brief reflects the fresh sync.
    if agent.has_event_autosync:
        try:
            res = agent.sync_predicthq_events()
            if res.get("ok"):
                print(f"[auto-synced {res.get('synced', '?')} PredictHQ event(s) into /api/events]")
            elif not res.get("skipped"):
                print(f"[PredictHQ auto-sync failed: {res.get('error')}]")
        except Exception as exc:  # noqa: BLE001
            log.exception("predicthq sync failed: %s", exc)
            print(f"[PredictHQ auto-sync skipped: {exc}]")

    print("\n=== Minot events (curated) ===")
    try:
        agent.refresh_minot_events()
        print(agent.minot_events_readout())
    except Exception as exc:  # noqa: BLE001
        log.exception("minot events read failed: %s", exc)
        print(f"[minot events read skipped: {exc}]")

    # ---- 1d. Nearby events (Ticketmaster Discovery — free key) ----
    print("\n=== Nearby events ===")
    try:
        if agent.has_events:
            agent.refresh_events()
            print(agent.events_readout())
        else:
            print("[no TICKETMASTER_API_KEY — add a free key to list nearby events]")
    except Exception as exc:  # noqa: BLE001
        log.exception("events read failed: %s", exc)
        print(f"[events read skipped: {exc}]")

    # ---- 2. Ruthless nightly command board ----
    await _step("Nightly command board", agent.nightly_command_board)

    # Weekly pulse on Mondays: a bigger-picture review rides along.
    if datetime.date.today().weekday() == 0:
        await _step("Weekly review", agent.weekly_review)

    # ---- 3. Tonight's angle + floor plan ----
    angle = agent.tonights_angle()
    if angle is None:
        print("\n[no promotable night angles configured — skipping tonight's plan]")
    else:
        print(f"\n=== Tonight's angle: {angle.title} ===")
        print(f"  {angle.angle}")
        await _step(f"Floor plan: {angle.title}", lambda a=angle: agent.plan_tonight(a))

        # ---- 4. Content pack for tonight's angle ----
        try:
            from agents.content_agent import BarContentAgent

            content_agent = BarContentAgent()
            print("\n=== CONTENT PACK ===")
            await _step(
                f"Instagram caption: {angle.title}",
                lambda a=angle: content_agent.write_caption(a, "instagram"),
            )
            await _step(
                f"TikTok short script: {angle.title}",
                lambda a=angle: content_agent.write_short_script(a, "tiktok"),
            )
        except Exception as exc:  # noqa: BLE001 - content is a bonus, never fatal
            log.exception("content pack failed: %s", exc)
            print(f"[content pack skipped: {exc}]")

        # ---- 4b. Tonight's cartoon strip (recurring cast) ----
        try:
            await _cartoons(agent, angle, today)
        except Exception as exc:  # noqa: BLE001 - cartoons are a bonus, never fatal
            log.exception("cartoon step failed: %s", exc)
            print(f"[cartoon skipped: {exc}]")

    # ---- 5. Loyalty nudge + busy-ness log prompt ----
    await _step("DrinkMinot tap nudge for tonight", agent.loyalty_nudge)
    print("\n=== BUSY-NESS LOG ===")
    print(agent.busyness_prompt(date=today))

    # ---- Self-improvement: record what to do differently, into the playbook ----
    learnings = await _step("Reflect (self-improvement)", agent.reflect)
    if learnings and str(learnings).strip():
        try:
            from agents import notes

            if notes.append_playbook(str(learnings), today=today):
                print("[playbook updated]")
        except Exception as exc:  # noqa: BLE001 - never fatal
            log.exception("playbook update failed: %s", exc)
            print(f"[playbook update skipped: {exc}]")

    agent.save()
    print(f"\n[state saved to {agent.state_path}]")


if __name__ == "__main__":
    asyncio.run(main())
