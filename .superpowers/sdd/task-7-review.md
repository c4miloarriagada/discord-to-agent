0686f2c feat(infra): discord notifier with embed and file helpers

 src/infrastructure/discord_adapter.py        | 100 +++++++++++++++++++++++++++
 tests/infrastructure/test_discord_adapter.py |  58 ++++++++++++++++
 2 files changed, 158 insertions(+)

diff --git a/src/infrastructure/discord_adapter.py b/src/infrastructure/discord_adapter.py
new file mode 100644
index 0000000..2e9c62e
--- /dev/null
+++ b/src/infrastructure/discord_adapter.py
@@ -0,0 +1,100 @@
+"""Discord implementation of the Notifier port."""
+
+from __future__ import annotations
+
+import io
+
+import discord
+
+from src.domain.interfaces import Notifier
+from src.domain.models import Prompt, Response
+
+EMBED_CHAR_LIMIT = 1900
+COLOR_SUCCESS = 0x2ECC71
+COLOR_FAILURE = 0xE74C3C
+COLOR_TIMEOUT = 0xF39C12
+
+
+def build_result_embed(prompt: Prompt, response: Response) -> discord.Embed:
+    """Build the embed for a run result."""
+    if response.timed_out:
+        title, color = f"⏱️ {response.agent_name} — timeout", COLOR_TIMEOUT
+    elif response.success:
+        title, color = f"✅ {response.agent_name} — done", COLOR_SUCCESS
+    else:
+        title, color = f"❌ {response.agent_name} — failed", COLOR_FAILURE
+    embed = discord.Embed(
+        title=title,
+        description=f"```{_truncate(response.output)}```",
+        color=color,
+    )
+    embed.add_field(name="Prompt", value=_truncate(prompt.text, 200), inline=False)
+    embed.set_footer(text=_footer(response))
+    return embed
+
+
+def build_error_embed(message: str) -> discord.Embed:
+    """Build a user-facing error embed."""
+    return discord.Embed(title="⚠️ Error", description=message, color=COLOR_FAILURE)
+
+
+def output_to_file(response: Response) -> discord.File | None:
+    """Attach the full output as a markdown file when it exceeds the embed limit."""
+    if len(response.output) <= EMBED_CHAR_LIMIT:
+        return None
+    buffer = io.BytesIO(response.output.encode())
+    return discord.File(buffer, filename="output.md")
+
+
+def _truncate(text: str, limit: int = EMBED_CHAR_LIMIT) -> str:
+    if len(text) <= limit:
+        return text
+    return text[: limit - 25] + "\n... (see attached file)"
+
+
+def _footer(response: Response) -> str:
+    parts = [f"{response.duration_seconds:.1f}s"]
+    if response.context_percent is not None:
+        parts.append(f"Context: {response.context_percent}%")
+    else:
+        parts.append("Context: n/a")
+    if response.session_id:
+        parts.append(response.session_id[:20])
+    return " · ".join(parts)
+
+
+class DiscordNotifier(Notifier):
+    """Sends results and errors to a Discord interaction or channel."""
+
+    def __init__(
+        self, target: discord.Interaction | discord.abc.Messageable, author_id: int
+    ) -> None:
+        self._target = target
+        self._author_id = author_id
+        self._view: discord.ui.View | None = None
+
+    def attach_view(self, view: discord.ui.View) -> None:
+        """Attach the approval view shown on result messages."""
+        self._view = view
+
+    async def send_result(self, prompt: Prompt, response: Response) -> None:
+        """Send the run result with mention, embed, optional file and view."""
+        kwargs: dict = {
+            "content": f"<@{self._author_id}>",
+            "embed": build_result_embed(prompt, response),
+            "view": self._view,
+        }
+        file = output_to_file(response)
+        if file is not None:
+            kwargs["file"] = file
+        await self._send(**kwargs)
+
+    async def send_error(self, message: str) -> None:
+        """Send a friendly error message."""
+        await self._send(embed=build_error_embed(message))
+
+    async def _send(self, **kwargs) -> None:
+        if isinstance(self._target, discord.Interaction):
+            await self._target.followup.send(**kwargs)
+        else:
+            await self._target.send(**kwargs)
diff --git a/tests/infrastructure/test_discord_adapter.py b/tests/infrastructure/test_discord_adapter.py
new file mode 100644
index 0000000..6dc93f3
--- /dev/null
+++ b/tests/infrastructure/test_discord_adapter.py
@@ -0,0 +1,58 @@
+"""Tests for Discord embed/file helpers (no connection needed)."""
+
+import discord
+
+from src.domain.models import Prompt, Response
+from src.infrastructure.discord_adapter import (
+    EMBED_CHAR_LIMIT,
+    build_error_embed,
+    build_result_embed,
+    output_to_file,
+)
+
+
+def make_response(**overrides) -> Response:
+    defaults = dict(output="ok", success=True, duration_seconds=1.5, agent_name="kimi")
+    return Response(**(defaults | overrides))
+
+
+def test_success_embed_is_green():
+    embed = build_result_embed(Prompt(text="hi", user_id=1), make_response())
+    assert embed.color == discord.Color(0x2ECC71)
+    assert "ok" in embed.description
+
+
+def test_failure_embed_is_red():
+    embed = build_result_embed(Prompt(text="hi", user_id=1), make_response(success=False))
+    assert embed.color == discord.Color(0xE74C3C)
+
+
+def test_timeout_embed_is_orange():
+    embed = build_result_embed(
+        Prompt(text="hi", user_id=1), make_response(success=False, timed_out=True)
+    )
+    assert embed.color == discord.Color(0xF39C12)
+
+
+def test_footer_shows_context_and_session():
+    response = make_response(context_percent=12.5, session_id="sess-abcdef")
+    embed = build_result_embed(Prompt(text="hi", user_id=1), response)
+    assert "12.5%" in embed.footer.text
+    assert "sess-abcdef" in embed.footer.text
+
+
+def test_footer_na_when_no_context():
+    embed = build_result_embed(Prompt(text="hi", user_id=1), make_response())
+    assert "n/a" in embed.footer.text
+
+
+def test_output_to_file_only_when_long():
+    assert output_to_file(make_response(output="short")) is None
+    file = output_to_file(make_response(output="x" * (EMBED_CHAR_LIMIT + 1)))
+    assert file is not None
+    assert file.filename == "output.md"
+
+
+def test_error_embed():
+    embed = build_error_embed("boom")
+    assert "boom" in embed.description
