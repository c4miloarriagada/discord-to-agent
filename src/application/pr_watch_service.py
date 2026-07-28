"""Use case: poll for new PR comments and surface them."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from src.domain.interfaces import PrCommentSource
from src.domain.models import PrComment

logger = structlog.get_logger(__name__)


class PrWatchService:
    """Tracks a watermark and returns only comments newer than it.

    The first check after startup sets a silent baseline so old comments
    are not re-notified on every bot restart.
    """

    def __init__(self, source: PrCommentSource, started_at: datetime | None = None) -> None:
        self._source = source
        self._since = started_at or datetime.now(timezone.utc)
        self._baseline_done = False

    async def check_new(self) -> list[PrComment]:
        """Return new comments since the last check (first call returns [])."""
        now = datetime.now(timezone.utc)
        comments = await self._source.fetch_new_comments(self._since)
        self._since = now
        if not self._baseline_done:
            self._baseline_done = True
            logger.info("pr_watch_baseline", found=len(comments))
            return []
        logger.info("pr_watch_poll", new=len(comments))
        return comments
