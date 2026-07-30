b6334b8 feat(interface): slash commands, approval buttons, message listener

 src/interface/bot.py                    | 125 +++++++++++++++++++++++++
 src/interface/commands.py               | 156 ++++++++++++++++++++++++++++++++
 src/interface/components.py             |  71 +++++++++++++++
 tests/interface/test_bot_text.py        |  61 +++++++++++++
 tests/interface/test_commands_guards.py |  28 ++++++
 tests/interface/test_components.py      |  24 +++++
 6 files changed, 465 insertions(+)

diff --git a/src/interface/bot.py b/src/interface/bot.py
new file mode 100644
index 0000000..d9e3dfe
--- /dev/null
+++ b/src/interface/bot.py
@@ -0,0 +1,125 @@
+"""Bot factory and entry point."""
+
+from __future__ import annotations
+
+import logging
+import sys
+
+import discord
+import structlog
+from discord.ext import commands
+
+from src.application.prompt_history import PromptHistory
+from src.domain.exceptions import ConfigError
+from src.infrastructure.agents.registry import create_agent_runner
+from src.infrastructure.config import Settings, load_settings
+from src.infrastructure.execution_tracker import InMemoryExecutionTracker
+from src.infrastructure.rate_limiter import InMemoryRateLimiter
+from src.infrastructure.session_store import InMemorySessionStore
+from src.interface.commands import (
+    AgentCog,
+    BotDeps,
+    channel_is_allowed,
+    run_prompt_flow,
+    user_is_allowed,
+)
+
+logger = structlog.get_logger(__name__)
+
+
+def create_bot(deps: BotDeps) -> commands.Bot:
+    """Build the Discord bot with slash commands and the message listener."""
+    intents = discord.Intents.default()
+    intents.message_content = True  # privileged intent: enable it in the Dev Portal
+
+    class AgentBot(commands.Bot):
+        async def setup_hook(self) -> None:
+            await self.add_cog(AgentCog(self, deps))
+            await self.tree.sync()
+
+    bot = AgentBot(command_prefix="!", intents=intents)
+
+    @bot.event
+    async def on_ready() -> None:
+        logger.info("bot_ready", user=str(bot.user), agent=deps.settings.agent_type)
+
+    @bot.event
+    async def on_message(message: discord.Message) -> None:
+        if message.author.bot:
+            return
+        text = _extract_prompt_text(message, bot)
+        if text is None:
+            return
+        if not user_is_allowed(deps.settings, message.author.id):
+            return
+        if message.guild is not None and not channel_is_allowed(
+            deps.settings, message.channel.id
+        ):
+            return
+        async with message.channel.typing():
+            await run_prompt_flow(text, message.author.id, message.channel, deps)
+
+    return bot
+
+
+def _extract_prompt_text(message: discord.Message, bot: commands.Bot) -> str | None:
+    """Return the prompt text when the message addresses the bot, else None."""
+    if message.guild is None:  # DM
+        return message.content.strip() or None
+    if bot.user and bot.user.mentioned_in(message):
+        text = message.content
+        for mention in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
+            text = text.replace(mention, "")
+        return text.strip() or None
+    reference = message.reference
+    if reference and isinstance(reference.resolved, discord.Message):
+        if reference.resolved.author == bot.user:
+            return message.content.strip() or None
+    return None
+
+
+def configure_logging(level: str) -> None:
+    """Configure structlog with a secret-stripping processor."""
+
+    def _strip_secrets(_logger, _method, event_dict):
+        for key in ("token", "discord_bot_token", "password", "secret"):
+            event_dict.pop(key, None)
+        return event_dict
+
+    structlog.configure(
+        processors=[
+            structlog.contextvars.merge_contextvars,
+            structlog.processors.add_log_level,
+            structlog.processors.TimeStamper(fmt="iso"),
+            _strip_secrets,
+            structlog.dev.ConsoleRenderer(),
+        ],
+        wrapper_class=structlog.make_filtering_bound_logger(
+            getattr(logging, level.upper(), logging.INFO)
+        ),
+    )
+
+
+def main() -> None:
+    """Entry point: build everything and run the bot."""
+    try:
+        settings = load_settings()
+        configure_logging(settings.log_level)
+        runner = create_agent_runner(settings)
+    except ConfigError as exc:
+        print(f"Configuration error: {exc}", file=sys.stderr)
+        sys.exit(1)
+    deps = BotDeps(
+        settings=settings,
+        runner=runner,
+        tracker=InMemoryExecutionTracker(),
+        rate_limiter=InMemoryRateLimiter(settings.rate_limit_seconds),
+        session_store=InMemorySessionStore(),
+        history=PromptHistory(),
+    )
+    bot = create_bot(deps)
+    bot.run(settings.discord_bot_token, log_handler=None)
+
+
+if __name__ == "__main__":
+    main()
diff --git a/src/interface/commands.py b/src/interface/commands.py
new file mode 100644
index 0000000..57b1fcc
--- /dev/null
+++ b/src/interface/commands.py
@@ -0,0 +1,156 @@
+"""Slash commands and the shared prompt flow."""
+
+from __future__ import annotations
+
+from dataclasses import dataclass
+
+import discord
+import structlog
+from discord import app_commands
+from discord.ext import commands
+
+from src.application.approval_service import ApprovalService
+from src.application.prompt_history import PromptHistory
+from src.application.prompt_service import PromptService
+from src.domain.exceptions import BotError
+from src.domain.interfaces import (
+    AgentRunner,
+    ExecutionTracker,
+    RateLimiter,
+    SessionStore,
+)
+from src.infrastructure.config import Settings
+from src.infrastructure.discord_adapter import DiscordNotifier, build_error_embed
+from src.interface.components import ApprovalView
+
+logger = structlog.get_logger(__name__)
+
+
+@dataclass
+class BotDeps:
+    """Shared dependencies injected into handlers."""
+
+    settings: Settings
+    runner: AgentRunner
+    tracker: ExecutionTracker
+    rate_limiter: RateLimiter
+    session_store: SessionStore
+    history: PromptHistory
+
+
+async def run_prompt_flow(
+    text: str,
+    user_id: int,
+    target: discord.Interaction | discord.abc.Messageable,
+    deps: BotDeps,
+) -> None:
+    """Shared entry point for /prompt and message-based prompts."""
+    notifier = DiscordNotifier(target, author_id=user_id)
+    service = PromptService(
+        runner=deps.runner,
+        tracker=deps.tracker,
+        rate_limiter=deps.rate_limiter,
+        session_store=deps.session_store,
+        history=deps.history,
+        notifier=notifier,
+    )
+    approval = ApprovalService(service, deps.history)
+    notifier.attach_view(ApprovalView(approval, author_id=user_id))
+    try:
+        await service.execute(text, user_id)
+    except BotError as exc:
+        await notifier.send_error(str(exc))
+    except Exception:
+        logger.exception("prompt_flow_failed")
+        await notifier.send_error("Unexpected error. Check the bot logs.")
+
+
+def user_is_allowed(settings: Settings, user_id: int) -> bool:
+    """Return True when no user restriction is set or the user is listed."""
+    return not settings.allowed_user_ids or user_id in settings.allowed_user_ids
+
+
+def channel_is_allowed(settings: Settings, channel_id: int | None) -> bool:
+    """Return True when no channel restriction is set or the channel is listed."""
+    return not settings.allowed_channel_ids or channel_id in settings.allowed_channel_ids
+
+
+class AgentCog(commands.Cog):
+    """Slash commands: /prompt /status /cancel /clear."""
+
+    def __init__(self, bot: commands.Bot, deps: BotDeps) -> None:
+        self.bot = bot
+        self._deps = deps
+
+    def _service(self) -> PromptService:
+        return PromptService(
+            runner=self._deps.runner,
+            tracker=self._deps.tracker,
+            rate_limiter=self._deps.rate_limiter,
+            session_store=self._deps.session_store,
+            history=self._deps.history,
+        )
+
+    async def _guard(self, interaction: discord.Interaction) -> bool:
+        allowed = user_is_allowed(
+            self._deps.settings, interaction.user.id
+        ) and channel_is_allowed(self._deps.settings, interaction.channel_id)
+        if not allowed:
+            await interaction.response.send_message(
+                "This bot does not operate here.", ephemeral=True
+            )
+        return allowed
+
+    @app_commands.command(name="prompt", description="Send a prompt to the coding agent")
+    async def prompt_cmd(self, interaction: discord.Interaction, text: str) -> None:
+        """Handle /prompt."""
+        if not await self._guard(interaction):
+            return
+        await interaction.response.defer()
+        await run_prompt_flow(text, interaction.user.id, interaction, self._deps)
+
+    @app_commands.command(name="status", description="Show the active execution and context usage")
+    async def status_cmd(self, interaction: discord.Interaction) -> None:
+        """Handle /status."""
+        if not await self._guard(interaction):
+            return
+        service = self._service()
+        current = service.current_execution()
+        context = service.context_percent(interaction.user.id)
+        context_text = f"{context}%" if context is not None else "n/a"
+        if current is None:
+            description = "No active execution."
+        else:
+            description = (
+                f"Running: `{current.prompt.text[:100]}`\n"
+                f"Elapsed: {current.elapsed_seconds:.0f}s"
+            )
+        embed = discord.Embed(title="📊 Status", description=description, color=0x3498DB)
+        embed.set_footer(text=f"Context: {context_text}")
+        await interaction.response.send_message(embed=embed)
+
+    @app_commands.command(name="cancel", description="Cancel the active execution")
+    async def cancel_cmd(self, interaction: discord.Interaction) -> None:
+        """Handle /cancel."""
+        if not await self._guard(interaction):
+            return
+        try:
+            await self._service().cancel()
+        except BotError as exc:
+            await interaction.response.send_message(
+                embed=build_error_embed(str(exc)), ephemeral=True
+            )
+            return
+        await interaction.response.send_message("🛑 Execution cancelled.")
+
+    @app_commands.command(
+        name="clear", description="Clear context: the next prompt starts a fresh session"
+    )
+    async def clear_cmd(self, interaction: discord.Interaction) -> None:
+        """Handle /clear."""
+        if not await self._guard(interaction):
+            return
+        self._service().clear_context(interaction.user.id)
+        await interaction.response.send_message(
+            "🧹 Context cleared. The next prompt starts a fresh session."
+        )
diff --git a/src/interface/components.py b/src/interface/components.py
new file mode 100644
index 0000000..883f3ec
--- /dev/null
+++ b/src/interface/components.py
@@ -0,0 +1,71 @@
+"""Discord UI components: approval buttons."""
+
+from __future__ import annotations
+
+import discord
+import structlog
+
+from src.application.approval_service import ApprovalService
+from src.domain.exceptions import BotError
+from src.infrastructure.discord_adapter import build_error_embed
+
+logger = structlog.get_logger(__name__)
+
+
+class ApprovalView(discord.ui.View):
+    """Approve / Reject / Retry buttons attached to every run result."""
+
+    def __init__(self, approval_service: ApprovalService, author_id: int) -> None:
+        super().__init__(timeout=900)
+        self._service = approval_service
+        self._author_id = author_id
+
+    async def interaction_check(self, interaction: discord.Interaction) -> bool:
+        """Only the prompt author may use these buttons."""
+        if interaction.user.id == self._author_id:
+            return True
+        await interaction.response.send_message(
+            "Only the prompt author can use these buttons.", ephemeral=True
+        )
+        return False
+
+    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
+    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
+        """Re-run the prompt with auto-approval."""
+        await interaction.response.defer()
+        await self._run(interaction, self._service.approve)
+
+    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji="❌")
+    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
+        """Discard the prompt and remove the buttons."""
+        await interaction.response.defer()
+        try:
+            await self._service.reject(interaction.user.id)
+        except BotError as exc:
+            await interaction.followup.send(
+                embed=build_error_embed(str(exc)), ephemeral=True
+            )
+            return
+        if interaction.message:
+            await interaction.message.edit(view=None)
+        await interaction.followup.send("🚫 Rejected.", ephemeral=True)
+
+    @discord.ui.button(label="Retry", style=discord.ButtonStyle.secondary, emoji="🔄")
+    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
+        """Re-run the prompt unchanged."""
+        await interaction.response.defer()
+        await self._run(interaction, self._service.retry)
+
+    async def _run(self, interaction: discord.Interaction, action) -> None:
+        try:
+            await action(interaction.user.id)
+        except BotError as exc:
+            await interaction.followup.send(
+                embed=build_error_embed(str(exc)), ephemeral=True
+            )
+        except Exception:
+            logger.exception("approval_action_failed")
+            await interaction.followup.send(
+                embed=build_error_embed("Unexpected error. Check the bot logs."),
+                ephemeral=True,
+            )
diff --git a/tests/interface/test_bot_text.py b/tests/interface/test_bot_text.py
new file mode 100644
index 0000000..6792630
--- /dev/null
+++ b/tests/interface/test_bot_text.py
@@ -0,0 +1,61 @@
+"""Tests for extracting prompt text from incoming messages."""
+
+from unittest.mock import MagicMock
+
+import discord
+
+from src.interface.bot import _extract_prompt_text
+
+
+def make_bot(bot_id: int = 999) -> MagicMock:
+    bot = MagicMock()
+    bot.user.id = bot_id
+    return bot
+
+
+def make_guild_message(content: str = "hi") -> MagicMock:
+    message = MagicMock()
+    message.guild = MagicMock()
+    message.content = content
+    message.reference = None
+    return message
+
+
+def test_dm_returns_content():
+    message = MagicMock()
+    message.guild = None
+    message.content = "hello there"
+    assert _extract_prompt_text(message, make_bot()) == "hello there"
+
+
+def test_mention_is_stripped():
+    bot = make_bot()
+    bot.user.mentioned_in.return_value = True
+    message = make_guild_message("<@999> fix the bug")
+    assert _extract_prompt_text(message, bot) == "fix the bug"
+
+
+def test_unrelated_guild_message_is_ignored():
+    bot = make_bot()
+    bot.user.mentioned_in.return_value = False
+    assert _extract_prompt_text(make_guild_message(), bot) is None
+
+
+def test_reply_to_bot_is_prompt():
+    bot = make_bot()
+    bot.user.mentioned_in.return_value = False
+    message = make_guild_message("and now do X")
+    resolved = MagicMock(spec=discord.Message)
+    resolved.author = bot.user
+    message.reference = MagicMock(resolved=resolved)
+    assert _extract_prompt_text(message, bot) == "and now do X"
+
+
+def test_reply_to_someone_else_is_ignored():
+    bot = make_bot()
+    bot.user.mentioned_in.return_value = False
+    message = make_guild_message("hello")
+    resolved = MagicMock(spec=discord.Message)
+    resolved.author = MagicMock()  # not the bot
+    message.reference = MagicMock(resolved=resolved)
+    assert _extract_prompt_text(message, bot) is None
diff --git a/tests/interface/test_commands_guards.py b/tests/interface/test_commands_guards.py
new file mode 100644
index 0000000..a8c4188
--- /dev/null
+++ b/tests/interface/test_commands_guards.py
@@ -0,0 +1,28 @@
+"""Tests for channel/user allowance guards."""
+
+from src.infrastructure.config import Settings
+from src.interface.commands import channel_is_allowed, user_is_allowed
+
+
+def settings(**overrides) -> Settings:
+    return Settings(discord_bot_token="x", **overrides)
+
+
+def test_user_allowed_when_no_restriction():
+    assert user_is_allowed(settings(), 1) is True
+
+
+def test_user_restriction():
+    restricted = settings(allowed_user_ids=[1, 2])
+    assert user_is_allowed(restricted, 2) is True
+    assert user_is_allowed(restricted, 3) is False
+
+
+def test_channel_allowed_when_no_restriction():
+    assert channel_is_allowed(settings(), 99) is True
+
+
+def test_channel_restriction():
+    restricted = settings(allowed_channel_ids=[10])
+    assert channel_is_allowed(restricted, 10) is True
+    assert channel_is_allowed(restricted, 99) is False
diff --git a/tests/interface/test_components.py b/tests/interface/test_components.py
new file mode 100644
index 0000000..f43261f
--- /dev/null
+++ b/tests/interface/test_components.py
@@ -0,0 +1,24 @@
+"""Tests for ApprovalView interaction checks."""
+
+from unittest.mock import AsyncMock, MagicMock
+
+from src.interface.components import ApprovalView
+
+
+def make_interaction(user_id: int) -> MagicMock:
+    interaction = MagicMock()
+    interaction.user.id = user_id
+    interaction.response.send_message = AsyncMock()
+    return interaction
+
+
+async def test_author_passes_check():
+    view = ApprovalView(approval_service=MagicMock(), author_id=42)
+    assert await view.interaction_check(make_interaction(42)) is True
+
+
+async def test_other_user_is_blocked():
+    view = ApprovalView(approval_service=MagicMock(), author_id=42)
+    interaction = make_interaction(7)
+    assert await view.interaction_check(interaction) is False
+    interaction.response.send_message.assert_awaited()
