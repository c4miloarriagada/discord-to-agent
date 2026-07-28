"""Slash commands and the shared prompt flow."""

from __future__ import annotations

from dataclasses import dataclass

import discord
import structlog
from discord import app_commands
from discord.ext import commands

from src.application.approval_service import ApprovalService
from src.application.prompt_history import PromptHistory
from src.application.prompt_service import PromptService
from src.domain.exceptions import BotError
from src.domain.interfaces import (
    AgentRunner,
    ExecutionTracker,
    RateLimiter,
    SessionStore,
)
from src.infrastructure.config import Settings
from src.infrastructure.discord_adapter import DiscordNotifier, build_error_embed
from src.interface.components import ApprovalView

logger = structlog.get_logger(__name__)


@dataclass
class BotDeps:
    """Shared dependencies injected into handlers."""

    settings: Settings
    runner: AgentRunner
    tracker: ExecutionTracker
    rate_limiter: RateLimiter
    session_store: SessionStore
    history: PromptHistory


async def run_prompt_flow(
    text: str,
    user_id: int,
    target: discord.Interaction | discord.abc.Messageable,
    deps: BotDeps,
) -> None:
    """Shared entry point for /prompt and message-based prompts."""
    notifier = DiscordNotifier(target, author_id=user_id)
    service = PromptService(
        runner=deps.runner,
        tracker=deps.tracker,
        rate_limiter=deps.rate_limiter,
        session_store=deps.session_store,
        history=deps.history,
        notifier=notifier,
    )
    approval = ApprovalService(service, deps.history)
    notifier.attach_view(ApprovalView(approval, author_id=user_id))
    try:
        await service.execute(text, user_id)
    except BotError as exc:
        await notifier.send_error(str(exc))
    except Exception:
        logger.exception("prompt_flow_failed")
        await notifier.send_error("Unexpected error. Check the bot logs.")


def user_is_allowed(settings: Settings, user_id: int) -> bool:
    """Return True when no user restriction is set or the user is listed."""
    return not settings.allowed_user_ids or user_id in settings.allowed_user_ids


def channel_is_allowed(settings: Settings, channel_id: int | None) -> bool:
    """Return True when no channel restriction is set or the channel is listed."""
    return not settings.allowed_channel_ids or channel_id in settings.allowed_channel_ids


def channel_check_passes(
    settings: Settings, guild_id: int | None, channel_id: int | None
) -> bool:
    """Apply the channel allowlist in guilds only; DMs always pass."""
    return guild_id is None or channel_is_allowed(settings, channel_id)


class AgentCog(commands.Cog):
    """Slash commands: /prompt /status /cancel /clear."""

    def __init__(self, bot: commands.Bot, deps: BotDeps) -> None:
        self.bot = bot
        self._deps = deps

    def _service(self) -> PromptService:
        return PromptService(
            runner=self._deps.runner,
            tracker=self._deps.tracker,
            rate_limiter=self._deps.rate_limiter,
            session_store=self._deps.session_store,
            history=self._deps.history,
        )

    async def _guard(self, interaction: discord.Interaction) -> bool:
        allowed = user_is_allowed(
            self._deps.settings, interaction.user.id
        ) and channel_check_passes(
            self._deps.settings, interaction.guild_id, interaction.channel_id
        )
        if not allowed:
            logger.info(
                "guard_rejected",
                user_id=interaction.user.id,
                channel_id=interaction.channel_id,
                guild_id=interaction.guild_id,
            )
            await interaction.response.send_message(
                "This bot does not operate here.", ephemeral=True
            )
        return allowed

    @app_commands.command(name="prompt", description="Send a prompt to the coding agent")
    async def prompt_cmd(self, interaction: discord.Interaction, text: str) -> None:
        """Handle /prompt."""
        if not await self._guard(interaction):
            return
        await interaction.response.defer()
        await run_prompt_flow(text, interaction.user.id, interaction, self._deps)

    @app_commands.command(name="status", description="Show the active execution and context usage")
    async def status_cmd(self, interaction: discord.Interaction) -> None:
        """Handle /status."""
        if not await self._guard(interaction):
            return
        service = self._service()
        current = service.current_execution()
        context = service.context_percent(interaction.user.id)
        context_text = f"{context}%" if context is not None else "n/a"
        session_id = self._deps.session_store.get(interaction.user.id)
        session_text = session_id[:20] if session_id else "none"
        if current is None:
            description = "No active execution."
        else:
            description = (
                f"Running: `{current.prompt.text[:100]}`\n"
                f"Elapsed: {current.elapsed_seconds:.0f}s"
            )
        embed = discord.Embed(title="📊 Status", description=description, color=0x3498DB)
        embed.set_footer(text=f"Context: {context_text} · Session: {session_text}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="cancel", description="Cancel the active execution")
    async def cancel_cmd(self, interaction: discord.Interaction) -> None:
        """Handle /cancel."""
        if not await self._guard(interaction):
            return
        try:
            await self._service().cancel()
        except BotError as exc:
            await interaction.response.send_message(
                embed=build_error_embed(str(exc)), ephemeral=True
            )
            return
        await interaction.response.send_message("🛑 Execution cancelled.")

    @app_commands.command(
        name="clear", description="Clear context: the next prompt starts a fresh session"
    )
    async def clear_cmd(self, interaction: discord.Interaction) -> None:
        """Handle /clear."""
        if not await self._guard(interaction):
            return
        self._service().clear_context(interaction.user.id)
        await interaction.response.send_message(
            "🧹 Context cleared. The next prompt starts a fresh session."
        )
