"""Tests for the Kimi Code CLI adapter."""

import json

from src.domain.models import Prompt
from src.infrastructure.agents.kimi import KimiAdapter


def test_build_command_basic():
    adapter = KimiAdapter()
    argv = adapter.build_command(Prompt(text="hello", user_id=1), session_id=None)
    assert argv == ["kimi", "-p", "hello", "--output-format", "stream-json"]


def test_build_command_with_approve_and_session():
    adapter = KimiAdapter(command="/usr/bin/kimi", auto_approve_flag="--auto")
    argv = adapter.build_command(
        Prompt(text="hi", user_id=1, auto_approve=True), session_id="sess-9"
    )
    assert argv == [
        "/usr/bin/kimi", "-p", "hi", "--output-format", "stream-json", "--auto",
        "-S", "sess-9",
    ]


def test_parse_output_stream_json():
    raw = "\n".join(
        [
            json.dumps({"role": "assistant", "content": "Hello"}),
            json.dumps({"role": "assistant", "content": "World"}),
            json.dumps(
                {"role": "meta", "type": "session.resume_hint", "session_id": "sess-1"}
            ),
        ]
    )
    result = KimiAdapter().parse_output(raw)
    assert result.text == "Hello\nWorld"
    assert result.session_id == "sess-1"


def test_parse_output_fallback_plain_text():
    result = KimiAdapter().parse_output("plain output\n")
    assert result.text == "plain output"
    assert result.session_id is None


def test_parse_output_ignores_non_dict_json():
    raw = "\n".join(
        [
            "null",
            json.dumps({"role": "assistant", "content": "Hello"}),
            "42",
            "[1, 2]",
            json.dumps(
                {"role": "meta", "type": "session.resume_hint", "session_id": "sess-1"}
            ),
        ]
    )
    result = KimiAdapter().parse_output(raw)
    assert result.text == "Hello"
    assert result.session_id == "sess-1"


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
                    "inputCacheRead": 40000,
                    "inputCacheCreation": 0,
                },
            }
        )
        + "\n"
    )
    adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
    assert adapter.get_context_percent("sess-1") == 10.0


def test_get_context_percent_missing_session(tmp_path):
    adapter = KimiAdapter(sessions_dir=str(tmp_path))
    assert adapter.get_context_percent("nope") is None


def _write_wire(tmp_path, lines):
    wire = tmp_path / "wd_x" / "sess-1" / "agents" / "main" / "wire.jsonl"
    wire.parent.mkdir(parents=True)
    wire.write_text("\n".join(lines) + "\n")
    return wire


def test_get_context_percent_ignores_non_dict_json_line(tmp_path):
    _write_wire(
        tmp_path,
        [
            "null",
            "42",
            "[1, 2]",
            json.dumps({"type": "usage.record", "usage": {"input": 50000, "output": 50000}}),
        ],
    )
    adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
    assert adapter.get_context_percent("sess-1") == 10.0


def test_get_context_percent_ignores_non_numeric_usage_values(tmp_path):
    _write_wire(
        tmp_path,
        [
            json.dumps(
                {
                    "type": "usage.record",
                    "usage": {"input": 90000, "output": 10000, "note": "n/a"},
                }
            ),
        ],
    )
    adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
    assert adapter.get_context_percent("sess-1") == 10.0


def test_get_context_percent_ignores_non_dict_usage(tmp_path):
    _write_wire(
        tmp_path,
        [
            json.dumps({"type": "usage.record", "usage": {"input": 90000, "output": 10000}}),
            json.dumps({"type": "usage.record", "usage": "high"}),
        ],
    )
    adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
    assert adapter.get_context_percent("sess-1") == 10.0
