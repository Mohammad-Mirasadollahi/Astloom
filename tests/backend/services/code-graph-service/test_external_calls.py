"""External CALL tagging and blast-radius exclusion."""

from __future__ import annotations

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.enums import CallConfidence, SymbolKind
from code_graph_service.domain.external_calls import (
    classify_external_call,
    is_blast_call_edge,
    is_external_call_id,
)
from code_graph_service.testing import InMemoryStore


def test_classify_external_call_strict_only():
    assert classify_external_call("len") == "builtin"
    assert classify_external_call("isinstance") == "builtin"
    assert classify_external_call("json.dumps") == "stdlib"
    assert classify_external_call("Path", import_aliases={"Path": "pathlib.Path"}) == (
        "imported_external"
    )
    # Ambiguous / heuristic cases must stay unclassified (→ unresolved on ingest).
    assert classify_external_call("path.is_file") is None
    assert classify_external_call("strip") is None
    assert classify_external_call("get") is None
    assert classify_external_call("login", import_aliases={"login": "app.auth.login"}) is None
    assert classify_external_call("missing_project_helper") is None
    # Real builtins still count (open is builtin, not a heuristic method tag).
    assert classify_external_call("open") == "builtin"


def test_blast_excludes_external_and_unresolved_targets():
    assert is_blast_call_edge(target_id="sym:p:mod.fn") is True
    assert (
        is_blast_call_edge(
            target_id="sym:p:mod.fn",
            confidence=CallConfidence.AMBIGUOUS,
        )
        is False
    )
    assert is_blast_call_edge(target_id="ext:call:p:len", metadata={"is_external": True}) is False
    assert is_blast_call_edge(target_id="unresolved:p:len") is False


def test_ingest_tags_external_calls_and_detect_changes_ignores_them():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "p")
    src = '''
def check_password(password):
    return len(password) > 8

def login(user, password):
    return check_password(password)
'''
    svc.ingest_file(
        scope,
        "a",
        "c1",
        "k1",
        {"file_path": "src/auth.py", "source": src, "language": "python"},
    )

    call_edges = [e for e in store.list_edges(scope) if e.rel_type == "CALLS"]
    external = [e for e in call_edges if e.confidence == CallConfidence.EXTERNAL]
    project = [e for e in call_edges if is_blast_call_edge(target_id=e.target_id, metadata=e.metadata)]

    assert external, "expected len() to be tagged external"
    assert all(e.metadata.get("is_external") for e in external)
    assert all(is_external_call_id(e.target_id) for e in external)
    assert any(e.metadata.get("call") == "len" for e in external)

    assert any(e.metadata.get("call") == "check_password" for e in project)
    assert not any(e.metadata.get("call") == "len" for e in project)

    ext_syms = [s for s in store.list_symbols(scope) if s.kind == SymbolKind.EXTERNAL]
    assert ext_syms

    report = svc.detect_changes(scope, ["src/auth.py"])
    # Risk still computed from project CALLS (login -> check_password), not len().
    assert report["changed_functions"]
    login_row = next(r for r in report["changed_functions"] if r["qualified_name"].endswith("login"))
    assert login_row["caller_count"] == 0
