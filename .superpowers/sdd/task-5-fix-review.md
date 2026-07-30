3956899 fix(infra): guard non-dict JSON in kimi adapter, safe pid mocking in runner tests

 src/infrastructure/agents/kimi.py                  | 10 +++-
 tests/infrastructure/agents/test_kimi_adapter.py   | 66 ++++++++++++++++++++++
 .../agents/test_subprocess_runner.py               | 20 ++++++-
 3 files changed, 91 insertions(+), 5 deletions(-)

diff --git a/src/infrastructure/agents/kimi.py b/src/infrastructure/agents/kimi.py
index e394a3b..6211f7f 100644
--- a/src/infrastructure/agents/kimi.py
+++ b/src/infrastructure/agents/kimi.py
@@ -51,51 +51,57 @@ class KimiAdapter(AgentAdapter):
 
     def parse_output(self, raw: str) -> ParseResult:
         """Parse stream-json lines into display text plus session id."""
         texts: list[str] = []
         session_id: str | None = None
         for line in raw.splitlines():
             try:
                 event = json.loads(line)
             except json.JSONDecodeError:
                 continue
+            if not isinstance(event, dict):
+                continue
             if event.get("role") == "assistant" and event.get("content"):
                 texts.append(str(event["content"]))
             if event.get("type") == "session.resume_hint":
                 session_id = event.get("session_id", session_id)
         if not texts and session_id is None:
             return ParseResult(text=raw.strip())
         return ParseResult(text="\n".join(texts).strip(), session_id=session_id)
 
     def get_context_percent(self, session_id: str) -> float | None:
         """Compute context usage from the session's wire.jsonl, if available."""
         wire = self._find_wire_log(session_id)
         if wire is None:
             return None
         usage = self._last_usage(wire)
         if usage is None:
             return None
-        total = sum(usage.values())
+        total = sum(v for v in usage.values() if isinstance(v, (int, float)))
         return round(100.0 * total / self._context_window, 1)
 
     def _find_wire_log(self, session_id: str) -> str | None:
         pattern = os.path.join(
             self._sessions_dir, "*", session_id, "agents", "main", "wire.jsonl"
         )
         matches = glob.glob(pattern)
         return matches[0] if matches else None
 
     @staticmethod
     def _last_usage(wire_path: str) -> dict[str, int] | None:
         usage: dict[str, int] | None = None
         try:
             with open(wire_path, encoding="utf-8") as handle:
                 for line in handle:
                     try:
                         event = json.loads(line)
                     except json.JSONDecodeError:
                         continue
+                    if not isinstance(event, dict):
+                        continue
                     if event.get("type") == "usage.record":
-                        usage = event.get("usage", usage)
+                        candidate = event.get("usage")
+                        if isinstance(candidate, dict):
+                            usage = candidate
         except OSError:
             return None
         return usage
diff --git a/tests/infrastructure/agents/test_kimi_adapter.py b/tests/infrastructure/agents/test_kimi_adapter.py
index bc76e0b..39f8328 100644
--- a/tests/infrastructure/agents/test_kimi_adapter.py
+++ b/tests/infrastructure/agents/test_kimi_adapter.py
@@ -37,20 +37,37 @@ def test_parse_output_stream_json():
     assert result.text == "Hello\nWorld"
     assert result.session_id == "sess-1"
 
 
 def test_parse_output_fallback_plain_text():
     result = KimiAdapter().parse_output("plain output\n")
     assert result.text == "plain output"
     assert result.session_id is None
 
 
+def test_parse_output_ignores_non_dict_json():
+    raw = "\n".join(
+        [
+            "null",
+            json.dumps({"role": "assistant", "content": "Hello"}),
+            "42",
+            "[1, 2]",
+            json.dumps(
+                {"role": "meta", "type": "session.resume_hint", "session_id": "sess-1"}
+            ),
+        ]
+    )
+    result = KimiAdapter().parse_output(raw)
+    assert result.text == "Hello"
+    assert result.session_id == "sess-1"
+
+
 def test_get_context_percent(tmp_path):
     wire = tmp_path / "wd_x" / "sess-1" / "agents" / "main" / "wire.jsonl"
     wire.parent.mkdir(parents=True)
     wire.write_text(
         json.dumps(
             {
                 "type": "usage.record",
                 "usage": {
                     "inputOther": 50000,
                     "output": 10000,
@@ -61,10 +78,59 @@ def test_get_context_percent(tmp_path):
         )
         + "\n"
     )
     adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
     assert adapter.get_context_percent("sess-1") == 10.0
 
 
 def test_get_context_percent_missing_session(tmp_path):
     adapter = KimiAdapter(sessions_dir=str(tmp_path))
     assert adapter.get_context_percent("nope") is None
+
+
+def _write_wire(tmp_path, lines):
+    wire = tmp_path / "wd_x" / "sess-1" / "agents" / "main" / "wire.jsonl"
+    wire.parent.mkdir(parents=True)
+    wire.write_text("\n".join(lines) + "\n")
+    return wire
+
+
+def test_get_context_percent_ignores_non_dict_json_line(tmp_path):
+    _write_wire(
+        tmp_path,
+        [
+            "null",
+            "42",
+            "[1, 2]",
+            json.dumps({"type": "usage.record", "usage": {"input": 50000, "output": 50000}}),
+        ],
+    )
+    adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
+    assert adapter.get_context_percent("sess-1") == 10.0
+
+
+def test_get_context_percent_ignores_non_numeric_usage_values(tmp_path):
+    _write_wire(
+        tmp_path,
+        [
+            json.dumps(
+                {
+                    "type": "usage.record",
+                    "usage": {"input": 90000, "output": 10000, "note": "n/a"},
+                }
+            ),
+        ],
+    )
+    adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
+    assert adapter.get_context_percent("sess-1") == 10.0
+
+
+def test_get_context_percent_ignores_non_dict_usage(tmp_path):
+    _write_wire(
+        tmp_path,
+        [
+            json.dumps({"type": "usage.record", "usage": {"input": 90000, "output": 10000}}),
+            json.dumps({"type": "usage.record", "usage": "high"}),
+        ],
+    )
+    adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
+    assert adapter.get_context_percent("sess-1") == 10.0
diff --git a/tests/infrastructure/agents/test_subprocess_runner.py b/tests/infrastructure/agents/test_subprocess_runner.py
index c9affde..804bfe5 100644
--- a/tests/infrastructure/agents/test_subprocess_runner.py
+++ b/tests/infrastructure/agents/test_subprocess_runner.py
@@ -28,21 +28,21 @@ class SessionAdapter(FakeAdapter):
 
     def get_context_percent(self, session_id: str) -> float | None:
         return 33.3 if session_id == "sess-7" else None
 
 
 def make_process(returncode: int | None = 0, output: bytes = b"hello") -> MagicMock:
     process = MagicMock()
     process.returncode = returncode
     process.communicate = AsyncMock(return_value=(output, b""))
     process.wait = AsyncMock()
-    process.pid = 99999  # nonexistent pid: killpg falls back to process.kill()
+    process.pid = 99999  # mocked pid; killpg is patched to fail in kill tests
     return process
 
 
 async def test_run_success():
     process = make_process()
     spawn = AsyncMock(return_value=process)
     with patch("asyncio.create_subprocess_exec", spawn):
         runner = SubprocessAgentRunner(FakeAdapter(), working_dir="/tmp", timeout_seconds=5)
         response = await runner.run(Prompt(text="hi", user_id=1))
     assert response.success is True
@@ -59,39 +59,53 @@ async def test_run_nonzero_exit_is_failure():
     with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
         runner = SubprocessAgentRunner(FakeAdapter(), "/tmp", 5)
         response = await runner.run(Prompt(text="hi", user_id=1))
     assert response.success is False
     assert response.output == "boom"
 
 
 async def test_run_timeout_kills_process():
     process = make_process(returncode=None)
     process.communicate = lambda: asyncio.sleep(60)
-    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
+    with (
+        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
+        # killpg must not signal a real process group if pid 99999 happens to exist
+        patch(
+            "src.infrastructure.agents.base.os.killpg",
+            side_effect=ProcessLookupError,
+        ),
+    ):
         runner = SubprocessAgentRunner(FakeAdapter(), "/tmp", timeout_seconds=1)
         response = await runner.run(Prompt(text="hi", user_id=1))
     assert response.timed_out is True
     assert response.success is False
     process.kill.assert_called()
 
 
 async def test_cancel_kills_active_process():
     process = make_process(returncode=None)
     started = asyncio.Event()
 
     async def communicate():
         started.set()
         await asyncio.sleep(60)
         return b"", b""
 
     process.communicate = communicate
-    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
+    with (
+        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
+        # killpg must not signal a real process group if pid 99999 happens to exist
+        patch(
+            "src.infrastructure.agents.base.os.killpg",
+            side_effect=ProcessLookupError,
+        ),
+    ):
         runner = SubprocessAgentRunner(FakeAdapter(), "/tmp", 60)
         task = asyncio.create_task(runner.run(Prompt(text="hi", user_id=1)))
         await started.wait()
         await runner.cancel()
         process.kill.assert_called()
     task.cancel()
     with pytest.raises(asyncio.CancelledError):
         await task
 
 
