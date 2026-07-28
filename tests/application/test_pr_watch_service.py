"""Tests for PrWatchService."""

from datetime import datetime, timedelta, timezone

from src.application.pr_watch_service import PrWatchService
from src.domain.interfaces import PrCommentSource
from src.domain.models import PrComment


def make_comment(author: str = "octocat") -> PrComment:
    return PrComment(
        repo="o/r",
        pr_number=1,
        pr_title="Fix",
        author=author,
        body="change this",
        url="https://example.com/1",
        kind="comment",
    )


class FakeSource(PrCommentSource):
    """Returns canned comments and records the watermarks it was called with."""

    def __init__(self, comments: list[PrComment]) -> None:
        self._comments = comments
        self.calls: list[datetime] = []

    async def fetch_new_comments(self, since: datetime) -> list[PrComment]:
        self.calls.append(since)
        return self._comments


async def test_first_check_sets_silent_baseline():
    service = PrWatchService(FakeSource([make_comment()]))
    assert await service.check_new() == []


async def test_second_check_returns_new_comments():
    service = PrWatchService(FakeSource([make_comment()]))
    await service.check_new()
    comments = await service.check_new()
    assert len(comments) == 1
    assert comments[0].author == "octocat"


async def test_watermark_starts_at_started_at():
    source = FakeSource([])
    start = datetime.now(timezone.utc) - timedelta(hours=1)
    service = PrWatchService(source, started_at=start)
    await service.check_new()
    assert source.calls[0] == start


async def test_no_new_comments_returns_empty():
    service = PrWatchService(FakeSource([]))
    await service.check_new()
    assert await service.check_new() == []
