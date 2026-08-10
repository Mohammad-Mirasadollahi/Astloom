"""Tests for the local Compose env helpers kept in ``remote_client`` (SSH removed)."""

from __future__ import annotations

from pathlib import Path

import pytest

from astloom_cli.remote_client import apply_compose_env_to_os, parse_env_file


def test_parse_env_file(tmp_path: Path):
    env = tmp_path / ".env.local"
    env.write_text(
        "# comment\nASTLOOM_POSTGRES_PORT=32232\nASTLOOM_POSTGRES_USER=astloom\n",
        encoding="utf-8",
    )
    parsed = parse_env_file(env)
    assert parsed["ASTLOOM_POSTGRES_PORT"] == "32232"
    assert parsed["ASTLOOM_POSTGRES_USER"] == "astloom"


def test_parse_env_file_missing_returns_empty(tmp_path: Path):
    assert parse_env_file(tmp_path / "missing.env") == {}


def test_apply_compose_env_to_os_sets_derived_dsns(tmp_path: Path):
    compose_dir = tmp_path / "backend" / "deployments" / "compose"
    compose_dir.mkdir(parents=True)
    (compose_dir / ".env.local").write_text(
        "ASTLOOM_POSTGRES_USER=astloom\n"
        "ASTLOOM_POSTGRES_PASSWORD=secret\n"
        "ASTLOOM_POSTGRES_PORT=32232\n"
        "ASTLOOM_POSTGRES_DATABASE=astloom\n"
        "ASTLOOM_NEO4J_BOLT_PORT=32233\n"
        "ASTLOOM_NEO4J_PASSWORD=secret\n",
        encoding="utf-8",
    )
    environ: dict[str, str] = {}
    apply_compose_env_to_os(environ, tmp_path)
    assert environ["ASTLOOM_DATABASE_URL"] == "postgresql://astloom:secret@127.0.0.1:32232/astloom"
    assert environ["ASTLOOM_NEO4J_URI"] == "bolt://127.0.0.1:32233"
    assert environ["ASTLOOM_MCP_STORE_MODE"] == "postgres"


def test_apply_compose_env_to_os_missing_file_fails_closed(tmp_path: Path):
    with pytest.raises(SystemExit):
        apply_compose_env_to_os({}, tmp_path)
