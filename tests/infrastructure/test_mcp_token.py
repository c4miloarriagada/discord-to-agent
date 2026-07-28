"""Tests for reading the GitHub token from a kimi mcp.json config."""

import json

from src.infrastructure.github_client import token_from_mcp_config


def test_reads_token_from_mcp_config(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "github": {"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_secret"}}
                }
            }
        )
    )
    assert token_from_mcp_config(str(cfg)) == "ghp_secret"


def test_returns_none_without_github_server(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"other": {}}}))
    assert token_from_mcp_config(str(cfg)) is None


def test_returns_none_for_missing_file(tmp_path):
    assert token_from_mcp_config(str(tmp_path / "nope.json")) is None


def test_returns_none_for_invalid_json(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text("not json")
    assert token_from_mcp_config(str(cfg)) is None
