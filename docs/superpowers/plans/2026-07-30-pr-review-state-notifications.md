# Plan: Distinctive Discord notifications for PR review state changes

Date: 2026-07-30
Spec: `docs/superpowers/specs/2026-07-30-pr-review-state-notifications.md`

Small, presentation-layer-only feature: dispatch the embed builder in
`src/interface/pr_watcher.py` on `PrComment.kind == "review"` and
`PrComment.body` (`"APPROVED"` / `"CHANGES_REQUESTED"`), keeping the existing
generic blue embed for everything else.

## Task 1: Add the three embed variants in `pr_watcher.py`

Files:
- `src/interface/pr_watcher.py`

Changes:
- In `build_pr_comment_embed(comment: PrComment)`, dispatch on
  `comment.kind == "review"` and exact body match:
  - body `"APPROVED"` → green embed (`0x2ECC71`), title `✅ PR #N approved`,
    fields Repo / Reviewer / PR, footer suggesting to reply to merge or work on it.
  - body `"CHANGES_REQUESTED"` → red embed (`0xE74C3C`), title
    `🔴 Changes requested on PR #N`, same fields and footer.
  - anything else → the existing generic blue embed, unchanged.
- Keep the current generic path byte-for-byte identical (title format, color
  `0x3498DB`, 500-char truncation, `"(no body)"` fallback, existing footer) so
  existing tests pass unmodified.

Acceptance criteria:
- No changes outside `src/interface/pr_watcher.py`.
- `make lint` / `make test` (or `pytest`) run clean with the new code.

## Task 2: Add unit tests for the three variants

Files:
- `tests/interface/test_pr_watcher.py`

Tests to add (using the existing `make_comment()` helper):
- `test_approved_review_embed` — `kind="review"`, `body="APPROVED"`: title
  contains `✅ PR #7 approved`, color `0x2ECC71`, url preserved, reviewer and PR
  fields present.
- `test_changes_requested_review_embed` — `kind="review"`,
  `body="CHANGES_REQUESTED"`: title contains `🔴 Changes requested on PR #7`,
  color `0xE74C3C`.
- `test_commented_review_keeps_generic_embed` — `kind="review"` with a
  non-matching body (e.g. `"COMMENTED"` or free text): generic title and color
  `0x3498DB`.

Acceptance criteria:
- `pytest tests/interface/test_pr_watcher.py` passes, including the pre-existing
  `test_pr_comment_embed` and `test_pr_comment_embed_empty_body` (unmodified).
- Full test suite passes: `pytest`.

## Task 3: Update README

Files:
- `README.md`

Changes:
- Section **"PR comment notifications (optional)"**: add the two new notification
  types (green "PR approved" for `APPROVED` reviews, red "Changes requested" for
  `CHANGES_REQUESTED` reviews) and note that all other activity keeps the generic
  blue embed.
- Section **"Usage"**: make sure it reflects the tool's actual features —
  `/prompt` `/status` `/cancel` `/clear`, mentions/DMs/replies as prompts,
  approval buttons (✅ ❌ 🔄), reply-context injection, the PR watcher, and the
  new approval / changes-requested notifications. Only fix what is actually
  missing or stale.

Acceptance criteria:
- The two README sections accurately describe current behavior; no other sections
  touched.
