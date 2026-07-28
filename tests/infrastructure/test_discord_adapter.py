"""Tests for Discord embed/file helpers (no connection needed)."""

import discord

from src.domain.models import Prompt, Response
from src.infrastructure.discord_adapter import (
    EMBED_CHAR_LIMIT,
    build_error_embed,
    build_result_embed,
    output_to_file,
)


def make_response(**overrides) -> Response:
    defaults = dict(output="ok", success=True, duration_seconds=1.5, agent_name="kimi")
    return Response(**(defaults | overrides))


def test_success_embed_is_green():
    embed = build_result_embed(Prompt(text="hi", user_id=1), make_response())
    assert embed.color == discord.Color(0x2ECC71)
    assert "ok" in embed.description


def test_failure_embed_is_red():
    embed = build_result_embed(Prompt(text="hi", user_id=1), make_response(success=False))
    assert embed.color == discord.Color(0xE74C3C)


def test_timeout_embed_is_orange():
    embed = build_result_embed(
        Prompt(text="hi", user_id=1), make_response(success=False, timed_out=True)
    )
    assert embed.color == discord.Color(0xF39C12)


def test_footer_shows_context_and_session():
    response = make_response(context_percent=12.5, session_id="sess-abcdef")
    embed = build_result_embed(Prompt(text="hi", user_id=1), response)
    assert "12.5%" in embed.footer.text
    assert "sess-abcdef" in embed.footer.text


def test_footer_na_when_no_context():
    embed = build_result_embed(Prompt(text="hi", user_id=1), make_response())
    assert "n/a" in embed.footer.text


def test_output_to_file_only_when_long():
    assert output_to_file(make_response(output="short")) is None
    file = output_to_file(make_response(output="x" * (EMBED_CHAR_LIMIT + 1)))
    assert file is not None
    assert file.filename == "output.md"


def test_error_embed():
    embed = build_error_embed("boom")
    assert "boom" in embed.description
