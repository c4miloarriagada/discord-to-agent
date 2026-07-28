"""Tests for extracting prompt text from incoming messages."""

from unittest.mock import MagicMock

import discord

from src.interface.bot import _extract_prompt_text


def make_bot(bot_id: int = 999) -> MagicMock:
    bot = MagicMock()
    bot.user.id = bot_id
    return bot


def make_guild_message(content: str = "hi") -> MagicMock:
    message = MagicMock()
    message.guild = MagicMock()
    message.content = content
    message.reference = None
    return message


def test_dm_returns_content():
    message = MagicMock()
    message.guild = None
    message.content = "hello there"
    assert _extract_prompt_text(message, make_bot()) == "hello there"


def test_mention_is_stripped():
    bot = make_bot()
    bot.user.mentioned_in.return_value = True
    message = make_guild_message("<@999> fix the bug")
    assert _extract_prompt_text(message, bot) == "fix the bug"


def test_unrelated_guild_message_is_ignored():
    bot = make_bot()
    bot.user.mentioned_in.return_value = False
    assert _extract_prompt_text(make_guild_message(), bot) is None


def test_reply_to_bot_is_prompt():
    bot = make_bot()
    bot.user.mentioned_in.return_value = False
    message = make_guild_message("and now do X")
    resolved = MagicMock(spec=discord.Message)
    resolved.author = bot.user
    message.reference = MagicMock(resolved=resolved)
    assert _extract_prompt_text(message, bot) == "and now do X"


def test_reply_to_someone_else_is_ignored():
    bot = make_bot()
    bot.user.mentioned_in.return_value = False
    message = make_guild_message("hello")
    resolved = MagicMock(spec=discord.Message)
    resolved.author = MagicMock()  # not the bot
    message.reference = MagicMock(resolved=resolved)
    assert _extract_prompt_text(message, bot) is None


def test_reply_context_extracts_embed_content():
    import discord as d

    from src.interface.bot import _reply_context

    bot = make_bot()
    embed = d.Embed(
        title="💬 New review comment on PR #61",
        description="change `foo();` please",
        url="https://gh/61",
    )
    embed.add_field(name="Repo", value="agrak-chile/task-service", inline=True)
    resolved = MagicMock(spec=d.Message)
    resolved.author = bot.user
    resolved.content = "<@123>"
    resolved.embeds = [embed]
    message = make_guild_message("apply this")
    message.reference = MagicMock(resolved=resolved)
    context = _reply_context(message, bot)
    assert "PR #61" in context
    assert "agrak-chile/task-service" in context
    assert "change `foo();` please" in context
    assert "https://gh/61" in context


def test_reply_context_none_for_plain_message():
    from src.interface.bot import _reply_context

    bot = make_bot()
    message = make_guild_message("hello")
    assert _reply_context(message, bot) is None
