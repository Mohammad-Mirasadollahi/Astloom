"""Regression: Neo4j Compose memory must stay env-overridable and above toy 512M defaults."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "backend" / "deployments" / "compose" / "compose.yaml"


def test_neo4j_compose_memory_defaults_are_env_overridable_and_not_512m():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "ASTLOOM_NEO4J_PAGECACHE_SIZE:-1G" in text
    assert "ASTLOOM_NEO4J_HEAP_INITIAL_SIZE:-4G" in text
    assert "ASTLOOM_NEO4J_HEAP_MAX_SIZE:-4G" in text
    assert "NEO4J_server_memory_heap_max__size: 512M" not in text
