# Task 7 Report: Discord adapter (notifier + embed helpers)

## Status: DONE

## Files created

- `src/infrastructure/discord_adapter.py` — Discord implementation of the `Notifier`
  port. Exports constants `EMBED_CHAR_LIMIT = 1900`, `COLOR_SUCCESS = 0x2ECC71`,
  `COLOR_FAILURE = 0xE74C3C`, `COLOR_TIMEOUT = 0xF39C12`; pure helpers
  `build_result_embed(prompt, response)`, `build_error_embed(message)`,
  `output_to_file(response)`; and class `DiscordNotifier(target, author_id)` with
  `attach_view(view)`, `send_result(prompt, response)`, `send_error(message)`.
  Private helpers `_truncate` and `_footer` (footer shows duration, context % or
  "n/a", and session id prefix). Outputs longer than 1900 chars are sent as an
  `output.md` file attachment with a truncated excerpt in the embed.
- `tests/infrastructure/test_discord_adapter.py` — 7 tests for the embed/file
  helpers (no Discord connection needed), written verbatim from the brief.

Both files were written verbatim from the task brief's code blocks. No deviations.

## Test commands run and exact outcomes

1. Step 2 (expected failure):
   `.venv/bin/pytest tests/infrastructure/test_discord_adapter.py -v`
   → 1 collection error: `ModuleNotFoundError: No module named
   'src.infrastructure.discord_adapter'` — as expected by the brief.

2. Step 4 (implementation green):
   `.venv/bin/pytest tests/infrastructure/test_discord_adapter.py -v`
   → `7 passed, 1 warning in 0.19s` (warning is a pre-existing
   DeprecationWarning about `audioop` from discord.py itself, unrelated).

3. Full-suite regression check: `.venv/bin/pytest`
   → `55 passed, 1 warning in 1.35s` — no regressions.

4. Lint: `.venv/bin/ruff check src/infrastructure/discord_adapter.py
   tests/infrastructure/test_discord_adapter.py`
   → `All checks passed!`

## Commit

```
0686f2c90aa07864ecdbf692ab653634ed4255ad
feat(infra): discord notifier with embed and file helpers
```
Committed exactly per the brief's Step 5 (only the two task files staged).

## Deviations

None. Code and tests match the brief verbatim.

## Concerns

- `DiscordNotifier` itself (its `send_result`/`send_error`/`_send` dispatch over
  `Interaction.followup` vs `Messageable.send`) is not covered by unit tests —
  the brief specifies tests only for the pure helpers. This matches the brief,
  but real send-path behavior will only be exercised by integration/manual
  testing in later tasks (bot wiring).
- The embed description wraps truncated output in a code fence (```), so the
  effective payload is `EMBED_CHAR_LIMIT` of output plus fence characters; this
  stays well under Discord's 4096-char embed description limit, so no issue.
- `_truncate` drops up to 25 chars from the tail before appending the marker
  (`text[: limit - 25]`), so truncated embeds are slightly shorter than the
  limit — harmless, full content ships in the attached file.
