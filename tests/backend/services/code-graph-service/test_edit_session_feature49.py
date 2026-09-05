"""Feature 49 / ADR 48: IDE-semantic edit session (Fake LS) + reconcile."""

from __future__ import annotations

from pathlib import Path

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.edit_session import FakeEditSession
from code_graph_service.domain.parsing_authority import (
    DURABLE_EDGE_REFERENCE_KIND,
    SESSION_EDGE_REFERENCE_KIND,
)
from code_graph_service.testing import InMemoryStore


def _scope() -> Scope:
    return Scope(tenant_id="t", workspace_id="w", project_id="p")


def _svc() -> CodeGraphService:
    return CodeGraphService(
        InMemoryStore(),
        edit_session_factory=lambda **_: FakeEditSession(language="python"),
    )


def test_ide_references_labeled_semantic(tmp_path: Path):
    root = tmp_path
    (root / "a.py").write_text("def hello():\n    return 1\n\nx = hello()\n", encoding="utf-8")
    svc = _svc()
    # cursor on hello in def hello
    out = svc.ide_references(root_path=str(root), file_path="a.py", line=0, character=4)
    assert out["available"] is True
    assert out["reference_kind"] == SESSION_EDGE_REFERENCE_KIND
    assert out["count"] >= 2


def test_ide_definition(tmp_path: Path):
    root = tmp_path
    (root / "a.py").write_text("def hello():\n    return 1\n\nx = hello()\n", encoding="utf-8")
    svc = _svc()
    out = svc.ide_definition(root_path=str(root), file_path="a.py", line=3, character=4)
    assert out["available"] is True
    assert out["reference_kind"] == SESSION_EDGE_REFERENCE_KIND
    assert out["count"] >= 1
    assert out["locations"][0]["line"] == 0


def test_ide_rename_applies_and_reconciles(tmp_path: Path):
    root = tmp_path
    (root / "a.py").write_text("def hello():\n    return 1\n\nx = hello()\n", encoding="utf-8")
    store = InMemoryStore()
    svc = CodeGraphService(
        store,
        edit_session_factory=lambda **_: FakeEditSession(language="python"),
    )
    scope = _scope()
    svc.ingest_file(
        scope,
        "actor",
        "c0",
        "i0",
        {
            "file_path": "a.py",
            "source": (root / "a.py").read_text(encoding="utf-8"),
            "language": "python",
        },
    )
    out = svc.ide_rename(
        root_path=str(root),
        file_path="a.py",
        line=0,
        character=4,
        new_name="greet",
        scope=scope,
        actor_id="actor",
        correlation_id="c1",
        idempotency_key="i1",
        run_sync=True,
    )
    assert out["available"] is True
    assert out["applied"] is True
    assert out["reference_kind"] == SESSION_EDGE_REFERENCE_KIND
    text = (root / "a.py").read_text(encoding="utf-8")
    assert "def greet()" in text
    assert "hello" not in text
    assert out["reconcile"]["reference_kind"] == DURABLE_EDGE_REFERENCE_KIND
    assert out["reconcile"]["reconciled"] is True
    names = {
        s.name
        for s in store.list_symbols(scope)
        if s.file_path == "a.py" and s.kind.value in {"function", "method", "class"}
    }
    assert "greet" in names
    assert "hello" not in names


def test_ide_definition_missing_root_is_validation_error(tmp_path: Path):
    import pytest
    from code_graph_service.domain.errors import ValidationError

    svc = _svc()
    missing = tmp_path / "no-such-tree"
    with pytest.raises(ValidationError, match="does not exist or is not visible"):
        svc.ide_definition(
            root_path=str(missing),
            file_path="a.py",
            line=0,
            character=0,
        )


def test_ide_tools_unavailable_without_factory_or_ls(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_LSP_EDIT_SESSION", "0")
    root = tmp_path
    (root / "a.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    svc = CodeGraphService(InMemoryStore())  # default factory, disabled
    out = svc.ide_references(root_path=str(root), file_path="a.py", line=0, character=4)
    assert out["available"] is False
    assert out["reference_kind"] == SESSION_EDGE_REFERENCE_KIND


def test_path_escape_rejected(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    svc = _svc()
    import pytest
    from code_graph_service.domain.errors import ValidationError

    with pytest.raises(ValidationError, match="escapes"):
        svc.ide_references(root_path=str(root), file_path="../a.py", line=0, character=0)


def test_structural_neighbors_kind():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = _scope()
    result = svc.ingest_file(
        scope,
        "a",
        "c",
        "i",
        {"file_path": "m.py", "source": "def a():\n    b()\n\ndef b():\n    return 1\n", "language": "python"},
    )
    # pick a function symbol
    symbols = [s for s in store.list_symbols(scope) if s.kind.value in {"function", "method"}]
    assert symbols
    payload = svc.structural_query(scope, symbols[0].id)
    assert payload["reference_kind"] == "structural"
