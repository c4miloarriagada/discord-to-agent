"""Discord implementation of the Notifier port."""

from __future__ import annotations

import io

import discord

from src.domain.interfaces import Notifier
from src.domain.models import Prompt, Response

EMBED_CHAR_LIMIT = 1900
COLOR_SUCCESS = 0x2ECC71
COLOR_FAILURE = 0xE74C3C
COLOR_TIMEOUT = 0xF39C12


def build_result_embed(prompt: Prompt, response: Response) -> discord.Embed:
    """Build the embed for a run result."""
    if response.timed_out:
        title, color = f"⏱️ {response.agent_name} — timeout", COLOR_TIMEOUT
    elif response.success:
        title, color = f"✅ {response.agent_name} — done", COLOR_SUCCESS
    else:
        title, color = f"❌ {response.agent_name} — failed", COLOR_FAILURE
    embed = discord.Embed(
        title=title,
        description=f"```{_truncate(response.output)}```",
        color=color,
    )
    embed.add_field(name="Prompt", value=_truncate(prompt.text, 200), inline=False)
    embed.set_footer(text=_footer(response))
    return embed


def build_error_embed(message: str) -> discord.Embed:
    """Build a user-facing error embed."""
    return discord.Embed(title="⚠️ Error", description=message, color=COLOR_FAILURE)


def output_to_file(response: Response) -> discord.File | None:
    """Attach the full output as a markdown file when it exceeds the embed limit."""
    if len(response.output) <= EMBED_CHAR_LIMIT:
        return None
    buffer = io.BytesIO(response.output.encode())
    return discord.File(buffer, filename="output.md")


def _truncate(text: str, limit: int = EMBED_CHAR_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 25] + "\n... (see attached file)"


def _footer(response: Response) -> str:
    parts = [f"{response.duration_seconds:.1f}s"]
    if response.context_percent is not None:
        parts.append(f"Context: {response.context_percent}%")
    else:
        parts.append("Context: n/a")
    if response.session_id:
        parts.append(response.session_id[:20])
    return " · ".join(parts)


class DiscordNotifier(Notifier):
    """Sends results and errors to a Discord interaction or channel."""

    def __init__(
        self, target: discord.Interaction | discord.abc.Messageable, author_id: int
    ) -> None:
        self._target = target
        self._author_id = author_id
        self._view: discord.ui.View | None = None

    def attach_view(self, view: discord.ui.View) -> None:
        """Attach the approval view shown on result messages."""
        self._view = view

    async def send_result(self, prompt: Prompt, response: Response) -> None:
        """Send the run result with mention, embed, optional file and view."""
        kwargs: dict = {
            "content": f"<@{self._author_id}>",
            "embed": build_result_embed(prompt, response),
            "view": self._view,
        }
        file = output_to_file(response)
        if file is not None:
            kwargs["file"] = file
        await self._send(**kwargs)

    async def send_error(self, message: str) -> None:
        """Send a friendly error message."""
        await self._send(embed=build_error_embed(message))

    async def _send(self, **kwargs) -> None:
        if isinstance(self._target, discord.Interaction):
            await self._target.followup.send(**kwargs)
        else:
            await self._target.send(**kwargs)
