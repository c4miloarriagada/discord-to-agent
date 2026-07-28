"""Tests for GitHubPrCommentSource with an injected fetcher (no network)."""

from datetime import datetime, timedelta, timezone

from src.infrastructure.github_client import GitHubPrCommentSource

SINCE = datetime.now(timezone.utc) - timedelta(hours=1)
NOW_ISO = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_fetcher(payloads: dict):
    async def fetch(path: str, params: dict):
        return payloads[path]

    return fetch


def pr_payload() -> list:
    return [{"number": 7, "title": "Fix bug"}]


def comment_payload(login: str = "reviewer") -> list:
    return [{"user": {"login": login}, "body": "looks wrong", "html_url": "https://gh/1"}]


async def test_collects_issue_and_review_comments():
    source = GitHubPrCommentSource(
        token="x",
        repos=["o/r"],
        fetcher=make_fetcher(
            {
                "/repos/o/r/pulls": pr_payload(),
                "/repos/o/r/issues/7/comments": comment_payload(),
                "/repos/o/r/pulls/7/comments": comment_payload("line-reviewer"),
                "/repos/o/r/pulls/7/reviews": [],
            }
        ),
    )
    comments = await source.fetch_new_comments(SINCE)
    assert {c.kind for c in comments} == {"comment", "review_comment"}
    assert all(c.pr_number == 7 and c.repo == "o/r" for c in comments)
    assert all(c.pr_title == "Fix bug" for c in comments)


async def test_filters_recent_reviews_and_uses_state_as_body():
    source = GitHubPrCommentSource(
        token="x",
        repos=["o/r"],
        fetcher=make_fetcher(
            {
                "/repos/o/r/pulls": pr_payload(),
                "/repos/o/r/issues/7/comments": [],
                "/repos/o/r/pulls/7/comments": [],
                "/repos/o/r/pulls/7/reviews": [
                    {
                        "user": {"login": "approver"},
                        "body": "",
                        "state": "APPROVED",
                        "html_url": "https://gh/r",
                        "submitted_at": NOW_ISO,
                    },
                    {
                        "user": {"login": "old"},
                        "body": "old review",
                        "state": "COMMENTED",
                        "html_url": "https://gh/old",
                        "submitted_at": "2000-01-01T00:00:00Z",
                    },
                ],
            }
        ),
    )
    comments = await source.fetch_new_comments(SINCE)
    assert len(comments) == 1
    assert comments[0].body == "APPROVED"
    assert comments[0].kind == "review"


async def test_ignored_authors_are_skipped():
    source = GitHubPrCommentSource(
        token="x",
        repos=["o/r"],
        ignored_authors=("me",),
        fetcher=make_fetcher(
            {
                "/repos/o/r/pulls": pr_payload(),
                "/repos/o/r/issues/7/comments": comment_payload("me"),
                "/repos/o/r/pulls/7/comments": [],
                "/repos/o/r/pulls/7/reviews": [],
            }
        ),
    )
    assert await source.fetch_new_comments(SINCE) == []


async def test_only_own_prs_are_watched():
    source = GitHubPrCommentSource(
        token="x",
        repos=["o/r"],
        ignored_authors=("me",),
        only_authored_by=("me",),
        fetcher=make_fetcher(
            {
                "/repos/o/r/pulls": [
                    {"number": 7, "title": "Mine", "user": {"login": "me"}},
                    {"number": 8, "title": "Theirs", "user": {"login": "other"}},
                ],
                "/repos/o/r/issues/7/comments": comment_payload("reviewer"),
                "/repos/o/r/pulls/7/comments": [],
                "/repos/o/r/pulls/7/reviews": [],
            }
        ),
    )
    comments = await source.fetch_new_comments(SINCE)
    assert len(comments) == 1
    assert comments[0].pr_number == 7


async def test_all_prs_watched_without_author_filter():
    fetcher_calls = []

    async def fetch(path: str, params: dict):
        fetcher_calls.append(path)
        if path.endswith("/pulls"):
            return [
                {"number": 7, "title": "Mine", "user": {"login": "me"}},
                {"number": 8, "title": "Theirs", "user": {"login": "other"}},
            ]
        return []

    source = GitHubPrCommentSource(token="x", repos=["o/r"], fetcher=fetch)
    await source.fetch_new_comments(SINCE)
    assert any("issues/8/comments" in p for p in fetcher_calls)
