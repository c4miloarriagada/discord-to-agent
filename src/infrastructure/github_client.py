"""GitHub implementation of the PrCommentSource port."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import structlog

from src.domain.interfaces import PrCommentSource
from src.domain.models import PrComment

logger = structlog.get_logger(__name__)

Fetcher = Callable[[str, dict[str, str]], Awaitable[Any]]
GITHUB_API = "https://api.github.com"
ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def token_from_mcp_config(path: str) -> str | None:
    """Read the GitHub PAT from a kimi mcp.json config, if present."""
    try:
        cfg = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
        servers = cfg.get("mcpServers", cfg)
        token = servers.get("github", {}).get("env", {}).get(
            "GITHUB_PERSONAL_ACCESS_TOKEN"
        )
        return token or None
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


class GitHubPrCommentSource(PrCommentSource):
    """Polls the GitHub REST API for new comments on open PRs."""

    def __init__(
        self,
        token: str,
        repos: list[str],
        ignored_authors: tuple[str, ...] = (),
        only_authored_by: tuple[str, ...] = (),
        fetcher: Fetcher | None = None,
    ) -> None:
        self._token = token
        self._repos = repos
        self._ignored = set(ignored_authors)
        self._only_authored_by = set(only_authored_by)
        self._injected_fetcher = fetcher

    async def fetch_new_comments(self, since: datetime) -> list[PrComment]:
        """Return comments on open PRs created at or after `since`."""
        if self._injected_fetcher is not None:
            return await self._collect(self._injected_fetcher, since)
        import aiohttp

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with aiohttp.ClientSession(headers=headers) as session:

            async def fetch(path: str, params: dict[str, str]) -> Any:
                async with session.get(GITHUB_API + path, params=params) as resp:
                    resp.raise_for_status()
                    return await resp.json()

            return await self._collect(fetch, since)

    async def _collect(self, fetch: Fetcher, since: datetime) -> list[PrComment]:
        results: list[PrComment] = []
        for repo in self._repos:
            prs = await fetch(f"/repos/{repo}/pulls", {"state": "open", "per_page": "50"})
            for pr in prs:
                if not self._pr_is_watched(pr):
                    continue
                results.extend(await self._fetch_pr_comments(fetch, repo, pr, since))
        return [c for c in results if c.author not in self._ignored]

    def _pr_is_watched(self, pr: dict) -> bool:
        """When only_authored_by is set, watch only those authors' PRs."""
        if not self._only_authored_by:
            return True
        author = (pr.get("user") or {}).get("login")
        return author in self._only_authored_by

    async def _fetch_pr_comments(
        self, fetch: Fetcher, repo: str, pr: dict, since: datetime
    ) -> list[PrComment]:
        number = pr["number"]
        title = pr.get("title", "")
        stamp = since.strftime(ISO_FORMAT)
        issue = await fetch(
            f"/repos/{repo}/issues/{number}/comments",
            {"since": stamp, "per_page": "100"},
        )
        review_comments = await fetch(
            f"/repos/{repo}/pulls/{number}/comments",
            {"since": stamp, "per_page": "100", "sort": "created", "direction": "asc"},
        )
        reviews = await fetch(
            f"/repos/{repo}/pulls/{number}/reviews", {"per_page": "100"}
        )
        found = [self._normalize(repo, number, title, c, "comment") for c in issue]
        found += [
            self._normalize(repo, number, title, c, "review_comment")
            for c in review_comments
        ]
        found += [
            c
            for r in reviews
            if (c := self._normalize_review(repo, number, title, r, since)) is not None
        ]
        return found

    @staticmethod
    def _normalize(
        repo: str, number: int, title: str, raw: dict, kind: str
    ) -> PrComment:
        return PrComment(
            repo=repo,
            pr_number=number,
            pr_title=title,
            author=raw["user"]["login"],
            body=raw.get("body") or "",
            url=raw["html_url"],
            kind=kind,
        )

    def _normalize_review(
        self, repo: str, number: int, title: str, raw: dict, since: datetime
    ) -> PrComment | None:
        submitted = self._parse_timestamp(raw.get("submitted_at"))
        if submitted is None or submitted < since:
            return None
        comment = self._normalize(repo, number, title, raw, "review")
        if not comment.body:
            comment = PrComment(
                repo=comment.repo,
                pr_number=comment.pr_number,
                pr_title=comment.pr_title,
                author=comment.author,
                body=raw.get("state", ""),
                url=comment.url,
                kind=comment.kind,
            )
        return comment

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, ISO_FORMAT).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
