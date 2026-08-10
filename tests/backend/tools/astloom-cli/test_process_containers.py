"""Unit tests for CLI process-scoped composition roots (Phase D DI)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CLI_SRC = ROOT / "backend" / "packages"
if str(CLI_SRC) not in sys.path:
    sys.path.insert(0, str(CLI_SRC))

from astloom_cli.process_containers import (  # noqa: E402
    clear_process_containers,
    get_docs_sync_service,
    get_graph_service,
)


class _FakeGraph:
    def __init__(self) -> None:
        self.graph = object()


class _FakeDocs:
    def __init__(self) -> None:
        self.service = object()


def setup_function() -> None:
    clear_process_containers()


def teardown_function() -> None:
    clear_process_containers()


def test_get_graph_service_reuses_same_instance_per_backend() -> None:
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return _FakeGraph()

    first = get_graph_service(backend="memory", factory=factory)
    second = get_graph_service(backend="memory", factory=factory)
    assert first is second
    assert calls["n"] == 1


def test_get_graph_service_isolates_backends() -> None:
    def factory_a():
        return _FakeGraph()

    def factory_b():
        return _FakeGraph()

    a = get_graph_service(backend="memory", factory=factory_a)
    b = get_graph_service(backend="neo4j", factory=factory_b)
    assert a is not b


def test_get_docs_sync_service_reuses_same_instance() -> None:
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return _FakeDocs()

    first = get_docs_sync_service(backend="postgres", factory=factory)
    second = get_docs_sync_service(backend="postgres", factory=factory)
    assert first is second
    assert calls["n"] == 1
