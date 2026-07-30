diff --git a/README.md b/README.md
index 3a58107..32b913e 100644
--- a/README.md
+++ b/README.md
@@ -132,40 +132,43 @@ To run a different agent in Docker:
 Note: the mounted CLI binary runs inside a Linux container, so it must be Linux-compatible (on macOS hosts, install a Linux build of the CLI into the mounted dir or install the CLI inside the image instead).
 
 ## Usage
 
 - `/prompt add a health endpoint to app.py` — run a prompt against the agent CLI
 - Mention the bot in an allowed channel, DM it, or reply to one of its results to continue the conversation — all act as prompts
 - On every result, press ✅ to re-run the last prompt with auto-approval, ❌ to discard it, or 🔄 to retry it
 - `/clear` — clear context; the next prompt starts a fresh session
 - `/status` — show the active run and context-window usage %
 - `/cancel` — kill the active run
+- Reply to any bot message (including PR notifications) and its content is injected as context for your next prompt
+- With the PR watcher enabled (see below), new PR activity posts a notification embed: green **PR approved** for `APPROVED` reviews, red **Changes requested** for `CHANGES_REQUESTED` reviews, and the generic blue embed for everything else
 
 ## PR comment notifications (optional)
 
 The bot can poll GitHub and notify you in Discord when someone comments on open PRs in your repos, so you can iterate on reviews with the agent from your phone.
 
 Configuration (`.env`):
 
 | Variable | Description | Default |
 |---|---|---|
 | `GITHUB_TOKEN` | GitHub PAT with PR read access. If empty, the bot falls back to the token in `~/.kimi-code/mcp.json` (the GitHub MCP server, if configured). | `""` |
 | `GITHUB_REPOS` | Comma-separated `owner/repo` list to watch. Feature is disabled when empty. | `[]` |
 | `GITHUB_USERNAME` | Your GitHub login; your own comments are not notified. | `""` |
 | `GITHUB_POLL_INTERVAL` | Seconds between polls. | `60` |
 | `NOTIFY_CHANNEL_ID` | Channel for notifications. Defaults to the first `ALLOWED_CHANNEL_IDS` entry. | unset |
 
 How it works:
 
 - Every `GITHUB_POLL_INTERVAL` seconds the bot lists open PRs in each repo and fetches issue comments, review comments, and reviews newer than the last poll.
 - The first poll after startup sets a silent baseline (no spam with old comments).
 - Each new comment posts an embed (repo, PR, author, body, link) mentioning the first `ALLOWED_USER_IDS` entry, so your phone pings.
+- Reviews get distinctive embeds: a green **✅ PR approved** embed for `APPROVED` reviews and a red **🔴 Changes requested** embed for `CHANGES_REQUESTED` reviews (both with Repo / Reviewer / PR fields). All other activity — issue comments, review comments, reviews with other states or with a text body — keeps the generic blue embed.
 - **Reply to the notification** and your reply becomes a prompt in your session — the agent (which has its own GitHub access via the kimi MCP config) can then fix the PR.
 
 ## Adding a new agent adapter
 
 1. Create `src/infrastructure/agents/claude.py` with a `ClaudeAdapter(AgentAdapter)` implementing `name` and `build_command` (`parse_output` and `get_context_percent` hooks are optional).
 2. Register it: `AGENT_ADAPTERS["claude"] = ClaudeAdapter.from_settings` in `registry.py`.
 3. Set `AGENT_TYPE=claude` in `.env`. Done — services, Discord, and Docker are unchanged.
 
 Minimal example (compiles against the contract in `src/infrastructure/agents/base.py`):
 
diff --git a/src/interface/pr_watcher.py b/src/interface/pr_watcher.py
index 77546d4..73e1a82 100644
--- a/src/interface/pr_watcher.py
+++ b/src/interface/pr_watcher.py
@@ -6,22 +6,59 @@ import discord
 import structlog
 from discord.ext import commands, tasks
 
 from src.application.pr_watch_service import PrWatchService
 from src.domain.models import PrComment
 from src.infrastructure.config import Settings
 
 logger = structlog.get_logger(__name__)
 
 
+_REVIEW_STATE_FOOTER = "Reply to this message to merge or work on it with the agent"
+
+
+def _build_review_state_embed(
+    comment: PrComment, title: str, color: int, review_text: str = ""
+) -> discord.Embed:
+    """Build the embed for an actionable review state (approved / changes requested).
+
+    ``review_text`` is the optional free text of the review, shown as the
+    description when present. With the current normalization a review carrying
+    text keeps that text in ``comment.body`` and never matches the exact state
+    strings, so this slot exists for future-proofing.
+    """
+    embed = discord.Embed(
+        title=title,
+        description=review_text[:500] or None,
+        url=comment.url,
+        color=color,
+    )
+    embed.add_field(name="Repo", value=comment.repo, inline=True)
+    embed.add_field(name="Reviewer", value=comment.author, inline=True)
+    embed.add_field(name="PR", value=comment.pr_title[:100], inline=False)
+    embed.set_footer(text=_REVIEW_STATE_FOOTER)
+    return embed
+
+
 def build_pr_comment_embed(comment: PrComment) -> discord.Embed:
     """Build the embed for a new PR comment notification."""
+    if comment.kind == "review":
+        if comment.body == "APPROVED":
+            return _build_review_state_embed(
+                comment, f"✅ PR #{comment.pr_number} approved", 0x2ECC71
+            )
+        if comment.body == "CHANGES_REQUESTED":
+            return _build_review_state_embed(
+                comment,
+                f"🔴 Changes requested on PR #{comment.pr_number}",
+                0xE74C3C,
+            )
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
diff --git a/tests/interface/test_pr_watcher.py b/tests/interface/test_pr_watcher.py
index f32b9db..0eddfb2 100644
--- a/tests/interface/test_pr_watcher.py
+++ b/tests/interface/test_pr_watcher.py
@@ -30,20 +30,44 @@ def test_pr_comment_embed():
     assert embed.url == "https://gh/1"
     assert "change this" in embed.description
     assert embed.color == discord.Color(0x3498DB)
 
 
 def test_pr_comment_embed_empty_body():
     embed = build_pr_comment_embed(make_comment(body=""))
     assert embed.description == "(no body)"
 
 
+def test_approved_review_embed():
+    embed = build_pr_comment_embed(make_comment(kind="review", body="APPROVED"))
+    assert "✅ PR #7 approved" in embed.title
+    assert embed.color == discord.Color(0x2ECC71)
+    assert embed.url == "https://gh/1"
+    fields = {field.name: field.value for field in embed.fields}
+    assert fields["Reviewer"] == "ana"
+    assert fields["PR"] == "Fix bug"
+
+
+def test_changes_requested_review_embed():
+    embed = build_pr_comment_embed(
+        make_comment(kind="review", body="CHANGES_REQUESTED")
+    )
+    assert "🔴 Changes requested on PR #7" in embed.title
+    assert embed.color == discord.Color(0xE74C3C)
+
+
+def test_commented_review_keeps_generic_embed():
+    embed = build_pr_comment_embed(make_comment(kind="review", body="COMMENTED"))
+    assert "💬 New review on PR #7" in embed.title
+    assert embed.color == discord.Color(0x3498DB)
+
+
 def settings(**overrides) -> Settings:
     base = {"discord_bot_token": "x", "allowed_user_ids": [], "allowed_channel_ids": []}
     return Settings(**(base | overrides))
 
 
 def test_resolve_notify_channel_prefers_explicit():
     s = settings(notify_channel_id=123, allowed_channel_ids=[456])
     assert resolve_notify_channel_id(s) == 123
 
 
