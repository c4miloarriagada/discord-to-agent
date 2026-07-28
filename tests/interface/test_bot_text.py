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
