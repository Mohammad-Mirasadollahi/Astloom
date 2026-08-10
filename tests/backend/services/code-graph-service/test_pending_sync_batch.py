"""Batch pending-sync for agent coding bursts."""

from __future__ import annotations

from code_graph_service.domain.freshness import FreshnessState
from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore


def test_mark_pending_many_coalesces_paths():
    state = FreshnessState()
    state.mark_pending_many(["a.py", "b.py", "a.py"])
    assert set(state.pending) == {"a.py", "b.py"}


def test_service_mark_files_pending_batch():
    svc = CodeGraphService(InMemoryStore())
    banner = svc.mark_files_pending(["src/a.py", "src/b.py"])
    assert banner["pending_count"] == 2
    assert set(banner["pending_files"]) == {"src/a.py", "src/b.py"}
