"""
Deterministic scaffolding for social content generation.

The creative work (hooks, captions, short scripts, visual briefs) is written by
the LLM in ``agents/content_agent.py``. Everything here is pure and testable
without an LLM: default hashtags, a posting schedule/calendar across platforms,
and Markdown rendering / export of a content plan.
"""

from __future__ import annotations

from datetime import date, timedelta

from .models import ContentFormat, NightAngle, Platform, SocialPost

PLATFORMS: tuple[Platform, ...] = ("tiktok", "instagram", "facebook")

# The native short/video format each platform rewards most.
PLATFORM_VIDEO_FORMAT: dict[Platform, ContentFormat] = {
    "tiktok": "short",
    "instagram": "reel",
    "facebook": "post",
}

_BASE_TAGS = ["#minotnd", "#downtownminot", "#northdakota", "#downunderminot"]
_STOPWORDS = {"the", "a", "an", "and", "of", "on", "in", "by", "with", "for", "to"}


def default_hashtags(angle: NightAngle, platform: Platform) -> list[str]:
    """A small, relevant hashtag set for a night angle + platform.

    Deduped and capped. Deliberately local-first (Minot / North Dakota); a bar
    grows on locals seeing it, not a tag wall.
    """
    tags = list(_BASE_TAGS)
    for token in angle.title.replace("/", " ").split():
        w = "".join(ch for ch in token.lower() if ch.isalnum())
        if len(w) > 2 and w not in _STOPWORDS:
            tag = f"#{w}"
            if tag not in tags:
                tags.append(tag)
    if platform == "tiktok":
        tags.append("#minottok")
    elif platform == "instagram":
        tags.append("#minotndeats")
    # Keep it tight — long tag walls read as spam.
    return tags[:12]


def posting_schedule(
    start: date,
    days: int = 14,
    per_week: int = 3,
    platforms: tuple[Platform, ...] = PLATFORMS,
) -> list[tuple[date, Platform]]:
    """A simple rotating calendar of (date, platform) slots.

    ``per_week`` posting days per week, spread evenly, rotating through the
    platforms so each gets regular coverage. Deterministic for a given input.
    """
    if per_week < 1:
        return []
    step = max(1, 7 // per_week)
    slots: list[tuple[date, Platform]] = []
    i = 0
    d = start
    while (d - start).days < days:
        slots.append((d, platforms[i % len(platforms)]))
        i += 1
        d = d + timedelta(days=step)
    return slots


def blank_plan_for_angle(
    angle: NightAngle,
    start: date,
    days: int = 14,
    per_week: int = 3,
) -> list[SocialPost]:
    """Skeleton posts on a schedule for one angle — hashtags + format filled,
    creative fields left for the LLM to write."""
    posts: list[SocialPost] = []
    for when, platform in posting_schedule(start, days, per_week):
        posts.append(
            SocialPost(
                platform=platform,
                format=PLATFORM_VIDEO_FORMAT[platform],
                related_angle_id=angle.id,
                hashtags=default_hashtags(angle, platform),
                status="idea",
                scheduled_for=when.isoformat(),
            )
        )
    return posts


def render_plan(angle_title: str, posts: list[SocialPost]) -> str:
    """A content plan / calendar as Markdown."""
    if not posts:
        return f"# Content plan: {angle_title}\n\nNo posts planned."
    out = [f"# Content plan: {angle_title}", "", f"{len(posts)} post(s).", ""]
    for post in posts:
        when = post.scheduled_for or "unscheduled"
        out.append(f"## {when} · {post.platform} · {post.format}")
        if post.hook:
            out.append(f"- **Hook:** {post.hook}")
        if post.caption:
            out.append(f"- **Caption:** {post.caption}")
        if post.script:
            out.append(f"- **Script:** {post.script}")
        if post.visual_brief:
            out.append(f"- **Visual:** {post.visual_brief}")
        if post.cta:
            out.append(f"- **CTA:** {post.cta}")
        if post.hashtags:
            out.append(f"- **Hashtags:** {' '.join(post.hashtags)}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
