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
