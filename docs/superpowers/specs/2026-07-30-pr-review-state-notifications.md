# Spec: Distinctive Discord notifications for PR review state changes

Date: 2026-07-30
Branch: main

## Goal

When a watched PR receives a new review, the bot should post a distinctive Discord
embed for the two actionable review states — `APPROVED` and `CHANGES_REQUESTED` —
instead of the generic blue "new comment" embed used for everything else.

## Background: how reviews are normalized today

- `src/infrastructure/github_client.py` (`GitHubPrCommentSource`) fetches issue
  comments, review comments, and reviews for open PRs and normalizes them all into
  `src/domain/models.py::PrComment` with `kind` in
  `{"comment", "review_comment", "review"}`.
- For reviews (`_normalize_review`): when the review has a text body, that body is
  used; when it has no text body, `PrComment.body` is set to the raw review state
  string (e.g. `"APPROVED"`, `"CHANGES_REQUESTED"`, `"COMMENTED"`).
- `src/interface/pr_watcher.py::build_pr_comment_embed` currently renders every
  `PrComment` with the same generic blue embed: title
  `"💬 New {kind} on PR #{n}"`, blue color `0x3498DB`, body in the description,
  fields for Repo / Author / PR title, and the footer
  `"Reply to this message to work on it with the agent"`.
- The polling loop `create_pr_watcher` already sends one message per `PrComment`
  via `build_pr_comment_embed`, so changing the builder alone changes the output
  for every notification.

## Behavior

Dispatch happens inside `build_pr_comment_embed(comment: PrComment)` in
`src/interface/pr_watcher.py`. The decision is based only on
`comment.kind == "review"` and the value of `comment.body` — no new data is needed.

### 1. Approved — green embed

Condition: `comment.kind == "review"` and `comment.body == "APPROVED"`.

- Title: `✅ PR #N approved` (N = `comment.pr_number`)
- Color: `0x2ECC71`
- URL: `comment.url` (PR/review link)
- Fields: `Repo` = `comment.repo` (inline), `Reviewer` = `comment.author` (inline),
  `PR` = `comment.pr_title` truncated to 100 chars (not inline)
- Footer: suggests replying to merge / work on it, e.g.
  `"Reply to this message to merge or work on it with the agent"`

### 2. Changes requested — red embed

Condition: `comment.kind == "review"` and `comment.body == "CHANGES_REQUESTED"`.

- Title: `🔴 Changes requested on PR #N`
- Color: `0xE74C3C`
- URL: `comment.url`
- Same fields as the approved variant (Repo, Reviewer, PR title)
- Footer: same suggestion as the approved variant
- When a non-empty review text is present, include it in the description. Note:
  with today's normalization, a review *with* text has `body` set to that text, so
  it will not match the exact `"CHANGES_REQUESTED"` condition and falls through to
  the generic embed. The description slot therefore exists for future-proofing and
  is documented behavior, not dead weight.

### 3. Everything else — existing generic blue embed

Reviews with other states (e.g. `COMMENTED`, `PENDING`), reviews that carry a text
body, issue comments (`kind == "comment"`), and review comments
(`kind == "review_comment"`) keep the existing embed exactly as-is: title
`"💬 New {kind} on PR #N"`, color `0x3498DB`, body (truncated to 500 chars, or
`"(no body)"`) as the description, and the existing footer. This path must remain
byte-for-byte compatible with current behavior so existing tests pass unchanged.

## Scope boundary

Presentation layer only. The entire change is the dispatch logic inside
`src/interface/pr_watcher.py` (either branching in `build_pr_comment_embed` or a
small private helper per variant). **No changes** to `github_client.py`, the domain
models, or the application layer — the state information needed is already present
in `PrComment`.

## Tests

Add unit tests in `tests/interface/test_pr_watcher.py` (reusing the existing
`make_comment()` helper):

- `test_approved_review_embed` — `kind="review"`, `body="APPROVED"`: asserts the
  `✅ PR #7 approved` title, green color `0x2ECC71`, URL, reviewer field, PR field.
- `test_changes_requested_review_embed` — `kind="review"`,
  `body="CHANGES_REQUESTED"`: asserts the `🔴 Changes requested on PR #7` title and
  red color `0xE74C3C`.
- `test_commented_review_keeps_generic_embed` — `kind="review"`, `body="COMMENTED"`
  (or a review with a text body): asserts the generic title and blue color
  `0x3498DB`, proving the fall-through.

Existing tests (`test_pr_comment_embed`, `test_pr_comment_embed_empty_body`) must
keep passing unmodified.

## README changes

- Section **"PR comment notifications (optional)"**: document the two new
  notification types — a green "PR approved" embed for `APPROVED` reviews and a red
  "Changes requested" embed for `CHANGES_REQUESTED` reviews — and note that all
  other activity keeps the generic blue embed.
- Section **"Usage"**: verify it is current with the tool's actual features —
  slash commands `/prompt`, `/status`, `/cancel`, `/clear`; mentions/DMs/replies as
  prompts; approval buttons (✅ re-run, ❌ discard, 🔄 retry); reply-context
  injection; the PR watcher; and the new approval / changes-requested
  notifications.

## Out of scope

- Changes to GitHub fetching, normalization, or polling logic.
- Notification deduplication or edited-review handling.
- Notifications for other review states (`COMMENTED`, `DISMISSED`, etc.).
- Configurable colors, titles, or toggles for the new embeds.
