# Feature Report: PR review state notifications

Date: 2026-07-30
Plan: `docs/superpowers/plans/2026-07-30-pr-review-state-notifications.md`
Spec: `docs/superpowers/specs/2026-07-30-pr-review-state-notifications.md`

## What changed

### `src/interface/pr_watcher.py`

- Added `_REVIEW_STATE_FOOTER = "Reply to this message to merge or work on it with the agent"`.
- Added private helper `_build_review_state_embed(comment, title, color, review_text="") -> discord.Embed`:
  builds the shared layout for actionable review states — `url=comment.url`, fields
  `Repo` (inline), `Reviewer` (inline), `PR` = `pr_title[:100]` (not inline), the
  review-state footer, and `description=review_text[:500] or None`. The description
  slot is the spec's future-proofing for reviews carrying free text (unreachable
  with today's normalization, documented in the docstring).
- `build_pr_comment_embed(comment)` now dispatches first on `comment.kind == "review"`:
  - `body == "APPROVED"` → green embed (`0x2ECC71`), title `✅ PR #N approved`.
  - `body == "CHANGES_REQUESTED"` → red embed (`0xE74C3C`), title `🔴 Changes requested on PR #N`.
  - Everything else falls through to the existing generic blue embed, which is
    byte-for-byte unchanged (title `"💬 New {kind} on PR #N"`, color `0x3498DB`,
    500-char truncation, `"(no body)"` fallback, original footer).

### `tests/interface/test_pr_watcher.py`

Added three tests using the existing `make_comment()` helper:

- `test_approved_review_embed` — `kind="review"`, `body="APPROVED"`: title contains
  `✅ PR #7 approved`, color `0x2ECC71`, url preserved, `Reviewer` and `PR` fields present.
- `test_changes_requested_review_embed` — `kind="review"`, `body="CHANGES_REQUESTED"`:
  title contains `🔴 Changes requested on PR #7`, color `0xE74C3C`.
- `test_commented_review_keeps_generic_embed` — `kind="review"`, `body="COMMENTED"`:
  generic title `💬 New review on PR #7`, color `0x3498DB` (proves the fall-through).

Pre-existing tests (`test_pr_comment_embed`, `test_pr_comment_embed_empty_body`,
channel-resolution tests) untouched.

### `README.md`

Only the two sections from the plan were touched:

- **Usage**: added a bullet for reply-context injection (replying to any bot
  message injects its content as context — verified in `src/interface/bot.py:83`)
  and a bullet describing the PR watcher notifications, including the new green
  "PR approved" and red "Changes requested" embeds.
- **PR comment notifications (optional)**: added a bullet documenting the two new
  notification types and noting that all other activity keeps the generic blue embed.

## TDD evidence

Tests were written first and run before the implementation:

```
$ .venv/bin/pytest tests/interface/test_pr_watcher.py -q
FAILED tests/interface/test_pr_watcher.py::test_approved_review_embed
FAILED tests/interface/test_pr_watcher.py::test_changes_requested_review_embed
2 failed, 6 passed, 1 warning in 0.34s
```

After implementing the dispatch:

```
$ .venv/bin/pytest tests/interface/test_pr_watcher.py -q
8 passed, 1 warning in 0.29s
```

## Final verification

```
$ .venv/bin/pytest -q
95 passed, 1 warning in 1.47s

$ .venv/bin/ruff check src tests
All checks passed!
```

(The single warning is a pre-existing `audioop` DeprecationWarning from discord.py,
unrelated to this change.)

## Deviations

None. Only the three allowed files were modified. No commits were made.
