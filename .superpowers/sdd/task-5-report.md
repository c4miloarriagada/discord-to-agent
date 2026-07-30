# Task 5 Report: Agent plugin system (base runner, Kimi adapter, registry)

## Status
DONE

## Commit
`4e9a61da717b012a2fdd2c841e3b9460fc9e2564` — `feat(infra): agent plugin system with kimi adapter` (branch `feat/discord-agent-bot`, 7 files, 437 insertions)

## Files created
- `src/infrastructure/agents/base.py` — `AgentAdapter` ABC (`name` property, `build_command`, `parse_output`, `get_context_percent`) and `SubprocessAgentRunner` implementing the `AgentRunner` port. Uses `asyncio.create_subprocess_exec` with argv list (no shell, verified by test asserting no `shell` kwarg), `start_new_session=True`, `asyncio.wait_for` timeout, and process-group kill via `os.killpg(SIGKILL)` with fallback to `process.kill()`.
- `src/infrastructure/agents/kimi.py` — `KimiAdapter` with `from_settings(settings)`; builds `kimi -p <text> --output-format stream-json [--yolo] [-S session]`, parses stream-json assistant content + `session.resume_hint` (plain-text fallback), computes context % from the session's `wire.jsonl` last `usage.record`.
- `src/infrastructure/agents/registry.py` — `AGENT_ADAPTERS` dict + `create_agent_runner(settings)`; raises `ConfigError("Unknown AGENT_TYPE ...")` for unregistered types.
- `tests/infrastructure/agents/__init__.py` (empty), `test_subprocess_runner.py` (5 tests), `test_kimi_adapter.py` (6 tests), `test_registry.py` (2 tests).

## Tests run
- Step 4 (red): `.venv/bin/pytest tests/infrastructure/agents -v` → 3 collection errors, `ModuleNotFoundError: No module named 'src.infrastructure.agents.base'`, as expected.
- Step 8 (green): `.venv/bin/pytest tests/infrastructure/agents -v` → **13 passed in 1.15s** (the brief predicted 12; the verbatim test files actually contain 13 tests: 5 + 6 + 2).
- Full suite: `.venv/bin/pytest` → **26 passed in 1.16s** (no regressions in earlier tasks' tests).
- Lint: `make lint` failed with `ruff: No such file or directory` (ruff not on PATH); ran `.venv/bin/ruff check src tests` → **All checks passed!**
- The 1s-timeout test (`test_run_timeout_kills_process`) passed as designed; not modified.

## Deviations
- Test count is 13, not the 12 stated in the brief's step 8 — the brief's own test code defines 13 tests. No code changed.
- Used `.venv/bin/ruff` instead of bare `ruff` for linting (ruff not installed on PATH).

## Security verification
- `shell=False` everywhere (argv-list `create_subprocess_exec` only; test asserts no `shell` kwarg).
- Subprocess timeout enforced via `asyncio.wait_for`.
- Process-group kill (`os.killpg` + `SIGKILL`) on timeout/cancel with `process.kill()` fallback; `start_new_session=True` ensures the group kill only hits the agent's tree.

## Concerns
None.

---

## Review fix report (post-review findings)

Commit: `3956899c1f3594a7296e38632ea35d5e123d632e` — "fix(infra): guard non-dict JSON in kimi adapter, safe pid mocking in runner tests"

### Finding 1 (Important): non-dict JSON payloads crashed output parsing
- `src/infrastructure/agents/kimi.py`
  - `parse_output`: after `json.loads(line)`, skip the line unless `isinstance(event, dict)`, so `null`, `42`, `[1, 2]` no longer raise `AttributeError` on `event.get(...)`.
  - `_last_usage`: same `isinstance(event, dict)` guard, and only adopt a `usage` value when it is itself a dict (`isinstance(candidate, dict)`), so a non-dict `usage` is ignored instead of crashing downstream.
  - `get_context_percent`: sum only numeric usage values: `sum(v for v in usage.values() if isinstance(v, (int, float)))`, so non-numeric values (e.g. `"note": "n/a"`) are skipped.
- `tests/infrastructure/agents/test_kimi_adapter.py` — 4 new tests (TDD: verified failing before the fix, passing after):
  - `test_parse_output_ignores_non_dict_json` — `null`, `42`, `[1, 2]` mixed with valid assistant/meta lines; text `"Hello"` and `session_id == "sess-1"` still returned.
  - `test_get_context_percent_ignores_non_dict_json_line` — non-dict JSON lines in wire.jsonl; still returns `10.0`.
  - `test_get_context_percent_ignores_non_numeric_usage_values` — string value in `usage`; still returns `10.0`.
  - `test_get_context_percent_ignores_non_dict_usage` — trailing `usage.record` with `usage: "high"`; earlier numeric record still used, returns `10.0`.
  - None handling unchanged (`test_get_context_percent_missing_session` still passes).

### Finding 2 (Minor, safety): pid 99999 could be a live pid
- `tests/infrastructure/agents/test_subprocess_runner.py`
  - `test_run_timeout_kills_process` and `test_cancel_kills_active_process` now patch `src.infrastructure.agents.base.os.killpg` with `side_effect=ProcessLookupError`, so `os.killpg` can never signal a real process group even if pid 99999 exists; the `process.kill()` fallback path is exercised deterministically. Existing assertions on `process.kill` kept.

### Test commands and outputs
- Red (before fix): `.venv/bin/pytest tests/infrastructure/agents -v` → 4 failed (the 4 new tests: `AttributeError` / `TypeError` as predicted), 13 passed.
- Green (after fix): `.venv/bin/pytest tests/infrastructure/agents -v` → **17 passed in 1.16s**.
- Full suite: `.venv/bin/pytest -q` → **30 passed in 1.17s**.
