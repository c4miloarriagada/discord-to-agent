"""Bot factory and entry point."""

from __future__ import annotations

import logging
import sys

import discord
import structlog
from discord.ext import commands, tasks

from src.application.pr_watch_service import PrWatchService
from src.application.prompt_history import PromptHistory
from src.domain.exceptions import ConfigError
from src.infrastructure.agents.registry import create_agent_runner
from src.infrastructure.config import load_settings
from src.infrastructure.execution_tracker import InMemoryExecutionTracker
from src.infrastructure.github_client import (
    GitHubPrCommentSource,
    token_from_mcp_config,
)
from src.infrastructure.rate_limiter import InMemoryRateLimiter
from src.infrastructure.session_store import InMemorySessionStore
from src.interface.commands import (
    AgentCog,
    BotDeps,
    channel_is_allowed,
    run_prompt_flow,
    user_is_allowed,
)
from src.interface.pr_watcher import create_pr_watcher, resolve_notify_channel_id

logger = structlog.get_logger(__name__)


def create_bot(deps: BotDeps) -> commands.Bot:
    """Build the Discord bot with slash commands and the message listener."""
    intents = discord.Intents.default()
    intents.message_content = True  # privileged intent: enable it in the Dev Portal

    class AgentBot(commands.Bot):
        async def setup_hook(self) -> None:
            await self.add_cog(AgentCog(self, deps))
            await self.tree.sync()
            watcher = _build_pr_watcher(self, deps)
            if watcher is not None:
                watcher.start()

    bot = AgentBot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready() -> None:
        logger.info("bot_ready", user=str(bot.user), agent=deps.settings.agent_type)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return
        text = _extract_prompt_text(message, bot)
        if text is None:
            return
        if not user_is_allowed(deps.settings, message.author.id):
            logger.info("message_rejected_user", user_id=message.author.id)
            return
        if message.guild is not None and not channel_is_allowed(
            deps.settings, message.channel.id
        ):
            logger.info(
                "message_rejected_channel",
                user_id=message.author.id,
                channel_id=message.channel.id,
            )
            return
        context = _reply_context(message, bot)
        async with message.channel.typing():
            await run_prompt_flow(
                text, message.author.id, message.channel, deps, context=context
            )

    return bot


def _reply_context(message: discord.Message, bot: commands.Bot) -> str | None:
    """Extract context from a referenced bot message (e.g. a PR notification)."""
    reference = message.reference
    if not reference or not isinstance(reference.resolved, discord.Message):
        return None
    resolved = reference.resolved
    if resolved.author != bot.user:
        return None
    parts: list[str] = []
    if resolved.content:
        parts.append(resolved.content)
    for embed in resolved.embeds:
        if embed.title:
            parts.append(embed.title)
        if embed.url:
            parts.append(embed.url)
        if embed.description:
            parts.append(embed.description)
        parts.extend(f"{f.name}: {f.value}" for f in embed.fields)
    context = "\n".join(p for p in parts if p).strip()
    return context or None


def _build_pr_watcher(bot: commands.Bot, deps: BotDeps) -> tasks.Loop | None:
    """Build the PR watcher loop, or None when it is not configured."""
    settings = deps.settings
    token = settings.github_token or token_from_mcp_config(settings.mcp_config_path)
    if not token or not settings.github_repos:
        logger.info("pr_watch_disabled", reason="missing token or repos")
        return None
    if resolve_notify_channel_id(settings) is None:
        logger.warning("pr_watch_disabled", reason="no notify channel configured")
        return None
    own_prs_only = bool(settings.github_username) and not settings.github_watch_all_prs
    source = GitHubPrCommentSource(
        token=token,
        repos=settings.github_repos,
        ignored_authors=(settings.github_username,) if settings.github_username else (),
        only_authored_by=(settings.github_username,) if own_prs_only else (),
    )
    logger.info(
        "pr_watch_enabled",
        repos=settings.github_repos,
        interval=settings.github_poll_interval,
    )
    return create_pr_watcher(bot, settings, PrWatchService(source))


def _extract_prompt_text(message: discord.Message, bot: commands.Bot) -> str | None:
    """Return the prompt text when the message addresses the bot, else None."""
    if message.guild is None:  # DM
        return message.content.strip() or None
    if bot.user and bot.user.mentioned_in(message):
        text = message.content
        for mention in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
            text = text.replace(mention, "")
        return text.strip() or None
    reference = message.reference
    if reference and isinstance(reference.resolved, discord.Message):
        if reference.resolved.author == bot.user:
            return message.content.strip() or None
    return None


def configure_logging(level: str) -> None:
    """Configure structlog with a secret-stripping processor."""

    def _strip_secrets(_logger, _method, event_dict):
        for key in ("token", "discord_bot_token", "password", "secret"):
            event_dict.pop(key, None)
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _strip_secrets,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
    )


def main() -> None:
    """Entry point: build everything and run the bot."""
    try:
        settings = load_settings()
        configure_logging(settings.log_level)
        runner = create_agent_runner(settings)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)
    deps = BotDeps(
        settings=settings,
        runner=runner,
        tracker=InMemoryExecutionTracker(),
        rate_limiter=InMemoryRateLimiter(settings.rate_limit_seconds),
        session_store=InMemorySessionStore(),
        history=PromptHistory(),
    )
    bot = create_bot(deps)
    bot.run(settings.discord_bot_token, log_handler=None)


if __name__ == "__main__":
    main()
