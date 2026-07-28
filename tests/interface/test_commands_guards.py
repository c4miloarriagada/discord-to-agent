"""Tests for channel/user allowance guards."""

from src.infrastructure.config import Settings
from src.interface.commands import (
    channel_check_passes,
    channel_is_allowed,
    user_is_allowed,
)


def settings(**overrides) -> Settings:
    """Build Settings detached from the local .env (tests must be hermetic)."""
    base = {"discord_bot_token": "x", "allowed_user_ids": [], "allowed_channel_ids": []}
    return Settings(**(base | overrides))


def test_user_allowed_when_no_restriction():
    assert user_is_allowed(settings(), 1) is True


def test_user_restriction():
    restricted = settings(allowed_user_ids=[1, 2])
    assert user_is_allowed(restricted, 2) is True
    assert user_is_allowed(restricted, 3) is False


def test_channel_allowed_when_no_restriction():
    assert channel_is_allowed(settings(), 99) is True


def test_channel_restriction():
    restricted = settings(allowed_channel_ids=[10])
    assert channel_is_allowed(restricted, 10) is True
    assert channel_is_allowed(restricted, 99) is False


def test_channel_check_skipped_in_dms():
    """DMs (guild_id is None) bypass the channel allowlist entirely."""
    restricted = settings(allowed_channel_ids=[10])
    assert channel_check_passes(restricted, guild_id=None, channel_id=99) is True
    assert channel_check_passes(restricted, guild_id=None, channel_id=None) is True


def test_channel_check_applies_in_guilds():
    """In guilds the channel allowlist is enforced."""
    restricted = settings(allowed_channel_ids=[10])
    assert channel_check_passes(restricted, guild_id=1, channel_id=10) is True
    assert channel_check_passes(restricted, guild_id=1, channel_id=99) is False


def test_channel_check_unrestricted():
    """Without a channel allowlist every location passes."""
    assert channel_check_passes(settings(), guild_id=1, channel_id=99) is True
    assert channel_check_passes(settings(), guild_id=None, channel_id=99) is True
