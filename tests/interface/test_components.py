"""Tests for ApprovalView interaction checks."""

from unittest.mock import AsyncMock, MagicMock

from src.interface.components import ApprovalView


def make_interaction(user_id: int) -> MagicMock:
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.response.send_message = AsyncMock()
    return interaction


async def test_author_passes_check():
    view = ApprovalView(approval_service=MagicMock(), author_id=42)
    assert await view.interaction_check(make_interaction(42)) is True


async def test_other_user_is_blocked():
    view = ApprovalView(approval_service=MagicMock(), author_id=42)
    interaction = make_interaction(7)
    assert await view.interaction_check(interaction) is False
    interaction.response.send_message.assert_awaited()
