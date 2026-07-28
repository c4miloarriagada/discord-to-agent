"""Discord UI components: approval buttons."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import discord
import structlog

from src.application.approval_service import ApprovalService
from src.domain.exceptions import BotError
from src.infrastructure.discord_adapter import build_error_embed

logger = structlog.get_logger(__name__)


class ApprovalView(discord.ui.View):
    """Approve / Reject / Retry buttons attached to every run result."""

    def __init__(self, approval_service: ApprovalService, author_id: int) -> None:
        super().__init__(timeout=900)
        self._service = approval_service
        self._author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only the prompt author may use these buttons."""
        if interaction.user.id == self._author_id:
            return True
        await interaction.response.send_message(
            "Only the prompt author can use these buttons.", ephemeral=True
        )
        return False

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Re-run the prompt with auto-approval."""
        await interaction.response.defer()
        await self._run(interaction, self._service.approve)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Discard the prompt and remove the buttons."""
        await interaction.response.defer()
        try:
            await self._service.reject(interaction.user.id)
        except BotError as exc:
            await interaction.followup.send(
                embed=build_error_embed(str(exc)), ephemeral=True
            )
            return
        if interaction.message:
            await interaction.message.edit(view=None)
        await interaction.followup.send("🚫 Rejected.", ephemeral=True)

    @discord.ui.button(label="Retry", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Re-run the prompt unchanged."""
        await interaction.response.defer()
        await self._run(interaction, self._service.retry)

    async def _run(
        self,
        interaction: discord.Interaction,
        action: Callable[[int], Awaitable[object]],
    ) -> None:
        try:
            await action(interaction.user.id)
        except BotError as exc:
            await interaction.followup.send(
                embed=build_error_embed(str(exc)), ephemeral=True
            )
        except Exception:
            logger.exception("approval_action_failed")
            await interaction.followup.send(
                embed=build_error_embed("Unexpected error. Check the bot logs."),
                ephemeral=True,
            )
