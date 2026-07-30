"""Tests for the PR watcher interface helpers."""

import discord

from src.domain.models import PrComment
from src.infrastructure.config import Settings
from src.interface.pr_watcher import (
    build_pr_comment_embed,
    resolve_notify_channel_id,
)


def make_comment(**overrides) -> PrComment:
    defaults = dict(
        repo="o/r",
        pr_number=7,
        pr_title="Fix bug",
        author="ana",
        body="change this",
        url="https://gh/1",
        kind="review_comment",
    )
    return PrComment(**(defaults | overrides))


def test_pr_comment_embed():
    embed = build_pr_comment_embed(make_comment())
    assert "PR #7" in embed.title
    assert "review comment" in embed.title
    assert embed.url == "https://gh/1"
    assert "change this" in embed.description
    assert embed.color == discord.Color(0x3498DB)


def test_pr_comment_embed_empty_body():
    embed = build_pr_comment_embed(make_comment(body=""))
    assert embed.description == "(no body)"


def test_approved_review_embed():
    embed = build_pr_comment_embed(make_comment(kind="review", body="APPROVED"))
    assert "✅ PR #7 approved" in embed.title
    assert embed.color == discord.Color(0x2ECC71)
    assert embed.url == "https://gh/1"
    fields = {field.name: field.value for field in embed.fields}
    assert fields["Reviewer"] == "ana"
    assert fields["PR"] == "Fix bug"


def test_changes_requested_review_embed():
    embed = build_pr_comment_embed(
        make_comment(kind="review", body="CHANGES_REQUESTED")
    )
    assert "🔴 Changes requested on PR #7" in embed.title
    assert embed.color == discord.Color(0xE74C3C)


def test_commented_review_keeps_generic_embed():
    embed = build_pr_comment_embed(make_comment(kind="review", body="COMMENTED"))
    assert "💬 New review on PR #7" in embed.title
    assert embed.color == discord.Color(0x3498DB)


def settings(**overrides) -> Settings:
    base = {"discord_bot_token": "x", "allowed_user_ids": [], "allowed_channel_ids": []}
    return Settings(**(base | overrides))


def test_resolve_notify_channel_prefers_explicit():
    s = settings(notify_channel_id=123, allowed_channel_ids=[456])
    assert resolve_notify_channel_id(s) == 123


def test_resolve_notify_channel_falls_back_to_first_allowed():
    s = settings(allowed_channel_ids=[456, 789])
    assert resolve_notify_channel_id(s) == 456


def test_resolve_notify_channel_none_without_config():
    assert resolve_notify_channel_id(settings()) is None
