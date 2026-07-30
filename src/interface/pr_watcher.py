"""Background task that notifies new PR comments to Discord."""

from __future__ import annotations

import discord
import structlog
from discord.ext import commands, tasks

from src.application.pr_watch_service import PrWatchService
from src.domain.models import PrComment
from src.infrastructure.config import Settings

logger = structlog.get_logger(__name__)


_REVIEW_STATE_FOOTER = "Reply to this message to merge or work on it with the agent"


def _build_review_state_embed(
    comment: PrComment, title: str, color: int, review_text: str = ""
) -> discord.Embed:
    """Build the embed for an actionable review state (approved / changes requested).

    ``review_text`` is the optional free text of the review, shown as the
    description when present. With the current normalization a review carrying
    text keeps that text in ``comment.body`` and never matches the exact state
    strings, so this slot exists for future-proofing.
    """
    embed = discord.Embed(
        title=title,
        description=review_text[:500] or None,
        url=comment.url,
        color=color,
    )
    embed.add_field(name="Repo", value=comment.repo, inline=True)
    embed.add_field(name="Reviewer", value=comment.author, inline=True)
    embed.add_field(name="PR", value=comment.pr_title[:100], inline=False)
    embed.set_footer(text=_REVIEW_STATE_FOOTER)
    return embed


def build_pr_comment_embed(comment: PrComment) -> discord.Embed:
    """Build the embed for a new PR comment notification."""
    if comment.kind == "review":
        if comment.body == "APPROVED":
            return _build_review_state_embed(
                comment, f"✅ PR #{comment.pr_number} approved", 0x2ECC71
            )
        if comment.body == "CHANGES_REQUESTED":
            return _build_review_state_embed(
                comment,
                f"🔴 Changes requested on PR #{comment.pr_number}",
                0xE74C3C,
            )
    embed = discord.Embed(
        title=f"💬 New {comment.kind.replace('_', ' ')} on PR #{comment.pr_number}",
        description=comment.body[:500] or "(no body)",
        url=comment.url,
        color=0x3498DB,
    )
    embed.add_field(name="Repo", value=comment.repo, inline=True)
    embed.add_field(name="Author", value=comment.author, inline=True)
    embed.add_field(name="PR", value=comment.pr_title[:100], inline=False)
    embed.set_footer(text="Reply to this message to work on it with the agent")
    return embed


def resolve_notify_channel_id(settings: Settings) -> int | None:
    """Pick the channel for PR notifications."""
    if settings.notify_channel_id is not None:
        return settings.notify_channel_id
    return settings.allowed_channel_ids[0] if settings.allowed_channel_ids else None


def create_pr_watcher(
    bot: commands.Bot, settings: Settings, service: PrWatchService
) -> tasks.Loop:
    """Create the polling loop that posts new PR comments to Discord."""
    channel_id = resolve_notify_channel_id(settings)
    mention = f"<@{settings.allowed_user_ids[0]}>" if settings.allowed_user_ids else None

    @tasks.loop(seconds=settings.github_poll_interval)
    async def watch() -> None:
        channel = bot.get_channel(channel_id)
        if channel is None:
            logger.warning("pr_watch_channel_missing", channel_id=channel_id)
            return
        try:
            comments = await service.check_new()
        except Exception:
            logger.exception("pr_watch_poll_failed")
            return
        for comment in comments:
            await channel.send(
                content=mention, embed=build_pr_comment_embed(comment)
            )

    @watch.before_loop
    async def _before() -> None:
        await bot.wait_until_ready()

    return watch
