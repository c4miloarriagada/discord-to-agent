"""Bot factory and entry point."""

from __future__ import annotations

import logging
import sys

import discord
import structlog
from discord.ext import commands

from src.application.prompt_history import PromptHistory
from src.domain.exceptions import ConfigError
from src.infrastructure.agents.registry import create_agent_runner
from src.infrastructure.config import load_settings
from src.infrastructure.execution_tracker import InMemoryExecutionTracker
from src.infrastructure.rate_limiter import InMemoryRateLimiter
from src.infrastructure.session_store import InMemorySessionStore
from src.interface.commands import (
    AgentCog,
    BotDeps,
    channel_is_allowed,
    run_prompt_flow,
    user_is_allowed,
)

logger = structlog.get_logger(__name__)


def create_bot(deps: BotDeps) -> commands.Bot:
    """Build the Discord bot with slash commands and the message listener."""
    intents = discord.Intents.default()
    intents.message_content = True  # privileged intent: enable it in the Dev Portal

    class AgentBot(commands.Bot):
        async def setup_hook(self) -> None:
            await self.add_cog(AgentCog(self, deps))
            await self.tree.sync()

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
        async with message.channel.typing():
            await run_prompt_flow(text, message.author.id, message.channel, deps)

    return bot


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
