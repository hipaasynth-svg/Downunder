# downunder

A NOOA agent that works one job: **get more customers into Down Under**
(downtown Minot, ND) tonight and this week — and turn that foot traffic into
**DrinkMinot** loyalty taps.

It's a **nightly-packet engine, not an autopilot.** It reads the live DrinkMinot
loyalty state, produces a short brief a human can act on in minutes, and learns
from a busy-ness log. **Nothing auto-publishes, and it never messages
customers** — the only email it sends is Cody's own brief to himself.

This is a fork of the sibling [`art-manager`](https://github.com/hipaasynth-svg/art-manager)
studio agent: it reuses that project's plumbing (nooa agent + lazy LLM, config,
Zoho mail, notes/playbook memory, a daily GitHub Action with a durable memory
branch, the content agent, and the voice lock) and swaps the art domain for a
bar + DrinkMinot domain.

## What the nightly brief contains

Run by `agents/run_nightly.py` (on a schedule via GitHub Actions):

1. **DrinkMinot loyalty pulse** — reads `GET /api/state`, reports the bar's live
   rating, taps, upvotes, reward, and happy hour, and flags honestly when
   DrinkMinot storage isn't attached (`persistent: false` → taps reset
   overnight).
2. **Nightly command board** — one highest-leverage move to get people in
   tonight, what to ignore, the pulse in a line, and one tap nudge to run at the
   bar.
3. **Tonight's angle + floor plan** — a promotable night (e-tabs for NDAD, the
   punch card, happy hour, weekend kickoff), rotating, with a Friday-specific
   angle.
4. **Content pack** — an Instagram caption + a TikTok script for tonight's
   angle, within the responsible-alcohol rules.
5. **Cartoon strip** — a recurring cast of Down Under characters stars in a short
   cartoon about tonight's angle. Rendered as an image when a Gemini key is set,
   otherwise written as a text storyboard. See below.
6. **Loyalty nudge + busy-ness log** — the honest way to earn more taps tonight,
   plus a prompt to rate tonight 1–5 at close (the measurement, since there are
   **no promo codes**).

## Cartoons (recurring cast)

The agent invents and **remembers** a small cast for the bar (e.g. a deadpan
bartender, a lucky-charm e-tab regular, a mascot), then draws a short cartoon
strip about each night. Keeping characters looking the same strip after strip is
the hard part, solved the field-standard way: each character gets **one locked
"canon" reference image**, generated once and fed into every future strip.

- **Model:** Google **Gemini 2.5 Flash Image ("Nano Banana")** via
  `agents/gemini.py` — best-in-class at "draw *this* character in a new scene,"
  ~$0.04/image, one API key, plain HTTP (runs from the Action).
- **Consistency:** canon references live in `cast/` and are persisted on the
  `downunder-state` branch, so the cast stays on-model across runs.
- **Degrades gracefully:** with no `GEMINI_API_KEY`, the strip is still written
  as a text storyboard (panels + dialogue) — the feature ships without the key
  and "turns on" when you add it.
- **Cast + scripts** are written by `agents/comic_agent.py`; the deterministic
  prompt-building and storyboard rendering live in `agents/cartoon.py`.

## The DrinkMinot tie-in

The bar is **venue id 63** on DrinkMinot. A customer taps the in-store tag at
`https://drinkminot.com/?r=63` to unlock a rating and start a punch card toward
a free item — no app, no account, no tracking. The agent only **reads** the
public state endpoint; it makes no changes to DrinkMinot.

> **Blocker to a durable funnel:** until an Upstash Redis store is attached to
> the DrinkMinot Vercel project, `/api/state` reports `persistent: false` and
> taps/ratings reset on every cold start. The agent reports this every run;
> attach the store before leaning on the punch card. (Vercel → drinkminot
> project → Storage → Upstash for Redis → redeploy.)

## Responsible alcohol

Baked into the voice lock (`VOICE_BIBLE.md`) and every agent prompt: 21+ only;
never target minors; never push volume or beat-the-clock drinking; charitable
gaming is about supporting NDAD and a good time, never chasing a win; promote
the place and the night, with a light "drink responsibly / grab a ride" nudge.

## Layout

| Path | What it is |
|------|-----------|
| `agents/downunder.py` | The agent — nightly command board, floor plan, loyalty nudge, reflect (LLM). |
| `agents/content_agent.py` | The content producer — captions + short scripts (LLM). |
| `agents/comic_agent.py` | The cartoonist — invents the recurring cast + writes strips (LLM). |
| `agents/cartoon.py` | Pure cartoon logic: image prompts + text storyboard. No LLM. |
| `agents/gemini.py` | Renders images via Gemini 2.5 Flash Image ("Nano Banana"). |
| `agents/drink.py` | Reads DrinkMinot `GET /api/state` → a `VenuePulse`. |
| `agents/logic.py` | Pure logic: pulse parsing, angle rotation, busy-ness rollup. No LLM. |
| `agents/models.py` | Pydantic models (`VenuePulse`, `NightAngle`, `BusynessEntry`, …). |
| `agents/content.py` | Deterministic content scaffolding (hashtags, schedule). |
| `agents/search.py` | Google Places (v2 nearby-venue recruiting; not wired into the nightly run). |
| `agents/{config,voice,notes,state,mail}.py` | Config, voice lock, memory, persistence, Zoho send. |
| `agents/run_nightly.py` | The nightly runner. |
| `VOICE_BIBLE.md` | Editable voice lock — change how it sounds here, not in code. |
| `BAR_NOTES.md` | Cody's between-run notes inbox (the agent honors it). |
| `PLAYBOOK.md` | What the agent has learned (auto-appended, human-prunable). |
| `.github/workflows/nightly.yml` | Runs nightly at 21:00 UTC; emails the brief; persists memory to the `downunder-state` branch. |

The data models and pure logic import without nooa, an API key, or network, so
the whole `tests/` suite runs on just `pydantic` + `pytest`.

## Run it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # required for the LLM parts
python -m agents.run_nightly        # prints the nightly brief

# tests (no nooa / API key needed)
pip install -r requirements-dev.txt
pytest -q
```

## Hook it up (GitHub Actions)

Add these repository **Secrets** (Settings → Secrets and variables → Actions):

- `ANTHROPIC_API_KEY` — **required** for the AI parts.
- `GEMINI_API_KEY` — *optional*: renders the nightly cartoon strip as an image
  (Google AI Studio; ~$0.04/image). Without it, the strip is a text storyboard.
- `ZOHO_MAIL_USER` / `ZOHO_MAIL_PASSWORD` — *optional*: emails you the nightly
  brief (use a Zoho **app password**), with the rendered strip attached. Without
  them the brief is still in the Actions log + a downloadable artifact.
- `DOWNUNDER_SEARCH_API_KEY` — *optional*: v2 nearby-venue scan (Google
  Places). Not used by the nightly run yet.

The workflow persists the agent's memory (`downunder_state.json` + `PLAYBOOK.md`)
to a `downunder-state` branch between runs, so each night continues where the last
left off.

## Configuration

Everything is env-overridable (`DOWNUNDER_*`); see `.env.example`. Point it at
a different bar by changing `DOWNUNDER_BAR_NAME`, `DOWNUNDER_VENUE_ID`, and
`DOWNUNDER_DRINK_URL` — no code change.
