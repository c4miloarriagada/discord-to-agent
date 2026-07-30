# Task 6 Report: Application services (history, prompt service, approval service)

## Status: DONE

Commit: `913fe80f48a6af1f333bbb61f66f17e34f32a90f` — `feat(app): prompt and approval services with history` (branch `feat/discord-agent-bot`)

## Files created

- `src/application/prompt_history.py` — `PromptHistory`: `record(prompt)`, `get(user_id)`, `clear(user_id)`; raises `NoPreviousPromptError` on missing entry.
- `src/application/prompt_service.py` — `PromptService`: `execute()`, `current_execution()`, `cancel()`, `clear_context()`, `context_percent()`; class attr `FORBIDDEN_TOKENS = (";", "|", "&&", "`", "$(")`; rejects empty/whitespace prompts via `_validate()`. Talks only to domain ports — no discord.py or subprocess imports. Logs `prompt_executed` via structlog.
- `src/application/approval_service.py` — `ApprovalService`: `approve()` (re-runs with `auto_approve=True`), `retry()` (re-runs preserving original `auto_approve`), `reject()` (clears history, returns `ApprovalStatus.REJECTED`).
- `tests/conftest.py` — shared fakes (`FakeRunner`, `FakeNotifier`, `AllowAllRateLimiter`) and fixtures wiring the in-memory adapters (`InMemoryExecutionTracker`, `InMemorySessionStore`).
- `tests/application/test_prompt_service.py` — 14 tests (incl. 6 parametrized dangerous-text cases).
- `tests/application/test_approval_service.py` — 4 tests.

## Test commands run and outcomes

1. `.venv/bin/pytest tests/application -v` (after conftest + tests, before implementations)
   → FAILED as expected: `ModuleNotFoundError: No module named 'src.application.prompt_history'` (TDD red phase).
2. `.venv/bin/pytest tests/application -v` (after implementations)
   → **18 passed in 0.06s**.
3. `.venv/bin/pytest` (full suite)
   → **48 passed in 1.19s** — no regressions in earlier tasks' tests.
4. `.venv/bin/ruff check src tests` (Makefile `lint` target)
   → **All checks passed!**

## Deviations

- Brief step 8 expected "all passed (17 tests)"; the actual count is 18 because the parametrized dangerous-text test expands to 6 cases (8 + 6 prompt-service tests + 4 approval-service tests = 18). The code was written verbatim from the brief; the "17" in the brief is simply a miscount, not a behavioral difference.

## Concerns

None. All code matches the brief verbatim, all constraints hold (English, type hints, Google-style docstrings, functions < 30 lines, no discord.py/subprocess in the application layer, forbidden-token sanitization covered by tests).
