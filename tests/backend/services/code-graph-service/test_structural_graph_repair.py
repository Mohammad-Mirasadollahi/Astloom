"""Regression: hash-stable edgeless FILE rows must re-ingest; knowledge_gaps signal."""

from __future__ import annotations

from pathlib import Path

import pytest

from code_graph_service.core import CodeGraphService, NotFoundError, Scope
from code_graph_service.domain.architecture import ArchNode, knowledge_gaps
from code_graph_service.domain.enums import RelType
from code_graph_service.domain.hashing import HASH_VERSION
from code_graph_service.domain.structural_integrity import file_needs_contains_repair
from code_graph_service.postgres_side import InMemoryEmbeddingIndex
from code_graph_service.testing import InMemoryStore


def test_file_needs_contains_repair_when_children_lack_contains():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "repair-unit")
    src = "def helper():\n    return 1\n\ndef main():\n    return helper()\n"
    svc.ingest_file(
        scope,
        "a",
        "c1",
        "k1",
        {"file_path": "src/mod.py", "source": src, "language": "python"},
    )
    file_id = f"file:{scope.project_id}:src/mod.py"
    assert file_needs_contains_repair(store, scope, file_id=file_id, file_path="src/mod.py") is False
    # Wipe CONTAINS edges while keeping symbols + FILE hash (simulates Neo4j edge loss).
    for edge in list(store.list_edges(scope, rel_type=RelType.CONTAINS.value)):
        store.delete_edge(scope, edge.id)
    assert file_needs_contains_repair(store, scope, file_id=file_id, file_path="src/mod.py") is True


def test_ingest_file_repairs_edgeless_hash_stable_file():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "repair-ingest")
    src = "def helper():\n    return 1\n\ndef main():\n    return helper()\n"
    svc.ingest_file(
        scope,
        "a",
        "c1",
        "k1",
        {"file_path": "src/mod.py", "source": src, "language": "python"},
    )
    file_id = f"file:{scope.project_id}:src/mod.py"
    for edge in list(store.list_edges(scope, rel_type=RelType.CONTAINS.value)):
        store.delete_edge(scope, edge.id)
    for edge in list(store.list_edges(scope, rel_type=RelType.CALLS.value)):
        store.delete_edge(scope, edge.id)
    assert not store.list_edges(scope, rel_type=RelType.CONTAINS.value, source_id=file_id)

    result = svc.ingest_file(
        scope,
        "a",
        "c2",
        "k2",
        {"file_path": "src/mod.py", "source": src, "language": "python"},
    )
    assert result.edges_written > 0
    contains = store.list_edges(scope, rel_type=RelType.CONTAINS.value, source_id=file_id)
    assert contains
    helper = next(s for s in store.list_symbols(scope) if s.name == "helper")
    callers = store.list_edges(scope, rel_type=RelType.CALLS.value, target_id=helper.id)
    assert callers


def test_sync_repo_repairs_edgeless_hash_stable_tree(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(
        "def helper():\n    return 1\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "repair-sync")
    svc.sync_repo(
        scope,
        "tester",
        "corr-1",
        "key-1",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    for edge in list(store.list_edges(scope, rel_type=RelType.CONTAINS.value)):
        store.delete_edge(scope, edge.id)
    again = svc.sync_repo(
        scope,
        "tester",
        "corr-2",
        "key-2",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    assert again.files_ingested >= 1
    assert again.mode != "noop"
    file_id = f"file:{scope.project_id}:src/a.py"
    assert store.list_edges(scope, rel_type=RelType.CONTAINS.value, source_id=file_id)


def test_sync_repo_reingests_when_hash_policy_version_changes(
    tmp_path: Path,
    monkeypatch,
):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(
        "def helper():\n    return 1\n",
        encoding="utf-8",
    )
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "repair-hash-version")
    import code_graph_service.domain.hashing as hashing

    monkeypatch.setattr(hashing, "HASH_VERSION", "legacy")
    svc.sync_repo(
        scope,
        "tester",
        "corr-1",
        "key-1",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    file_id = f"file:{scope.project_id}:src/a.py"
    assert store.get_symbol(file_id, scope).hash_version == "legacy"
    monkeypatch.setattr(hashing, "HASH_VERSION", HASH_VERSION)

    again = svc.sync_repo(
        scope,
        "tester",
        "corr-2",
        "key-1",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )

    assert again.files_ingested == 1
    assert store.get_symbol(file_id, scope).hash_version == HASH_VERSION


def test_sync_repo_prunes_symbols_and_embeddings_for_removed_source(tmp_path: Path):
    (tmp_path / "src").mkdir()
    active = tmp_path / "src" / "active.py"
    removed = tmp_path / "src" / "removed.py"
    active.write_text("def active():\n    return 1\n", encoding="utf-8")
    removed.write_text("def removed():\n    return 2\n", encoding="utf-8")
    store = InMemoryStore()
    embeddings = InMemoryEmbeddingIndex()
    svc = CodeGraphService(store, embedding_index=embeddings)
    scope = Scope("t", "w", "repair-deleted-file")

    svc.sync_repo(
        scope,
        "tester",
        "corr-1",
        "key-1",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    removed_file_id = f"file:{scope.project_id}:src/removed.py"
    removed_symbol_id = f"sym:{scope.project_id}:src.removed.removed"
    assert store.get_symbol(removed_file_id, scope)
    assert removed_symbol_id in embeddings.list_symbol_models(scope)

    removed.unlink()
    svc.sync_repo(
        scope,
        "tester",
        "corr-2",
        "key-2",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )

    with pytest.raises(NotFoundError):
        store.get_symbol(removed_file_id, scope)
    with pytest.raises(NotFoundError):
        store.get_symbol(removed_symbol_id, scope)
    assert removed_symbol_id not in embeddings.list_symbol_models(scope)
    assert store.get_symbol(f"file:{scope.project_id}:src/active.py", scope)


def test_sync_repo_backfills_language_without_rebuilding_edges(tmp_path: Path):
    source = tmp_path / "module.py"
    source.write_text("def helper():\n    return 1\n", encoding="utf-8")
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "repair-language")
    svc.sync_repo(
        scope,
        "tester",
        "corr-1",
        "key-1",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    for symbol in store.list_symbols_for_file(scope, "module.py"):
        symbol.language = ""
        store.put_symbol(symbol)

    result = svc.sync_repo(
        scope,
        "tester",
        "corr-2",
        "key-2",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )

    assert result.files_ingested == 1
    assert result.edges_written == 0
    assert all(
        symbol.language == "python"
        for symbol in store.list_symbols_for_file(scope, "module.py")
    )


def test_knowledge_gaps_isolation_uses_structural_degree_zero():
    nodes = [
        ArchNode("a", "orphan", "pkg.orphan", "a.py", "function"),
        ArchNode("b", "leaf", "pkg.leaf", "a.py", "function"),
        ArchNode("c", "hub", "pkg.hub", "a.py", "function"),
    ]
    edges = [
        ("file", "a", "CONTAINS"),
        ("file", "b", "CONTAINS"),
        ("file", "c", "CONTAINS"),
        ("b", "c", "CALLS"),
        ("c", "b", "CALLS"),
    ]
    gaps = knowledge_gaps(nodes, edges, tested_targets=set())
    isolated_ids = {row["symbol_id"] for row in gaps["isolated_nodes"]}
    assert "a" in isolated_ids
    assert "b" not in isolated_ids
    assert "c" not in isolated_ids


def test_knowledge_gaps_marks_call_tested_hotspots():
    nodes = [
        ArchNode("prod", "login", "pkg.login", "src/auth.py", "function"),
        ArchNode("test", "test_login", "tests.test_auth.test_login", "tests/test_auth.py", "function"),
    ]
    # High degree via many fake edges so prod would be a hotspot if untested.
    edges = [("prod", f"x{i}", "CALLS") for i in range(5)]
    edges.append(("test", "prod", "CALLS"))
    gaps = knowledge_gaps(nodes, edges, tested_targets={"prod"})
    assert gaps["untested_hotspots"] == []


def test_architecture_overview_uses_test_call_coverage():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "tested-calls")
    prod_src = "\n".join(
        [
            "def login():",
            "    return True",
            "",
            "def a():",
            "    return login()",
            "",
            "def b():",
            "    return login()",
            "",
            "def c():",
            "    return login()",
            "",
            "def d():",
            "    return login()",
        ]
    )
    svc.ingest_file(
        scope,
        "a",
        "c1",
        "k1",
        {"file_path": "src/auth.py", "source": prod_src, "language": "python"},
    )
    svc.ingest_file(
        scope,
        "a",
        "c2",
        "k2",
        {
            "file_path": "tests/test_auth.py",
            "source": "def test_login():\n    assert True\n",
            "language": "python",
        },
    )
    # Ensure a CALLS edge from test → login (convention TESTED_BY may also exist).
    login = next(s for s in store.list_symbols(scope) if s.name == "login")
    test_fn = next(s for s in store.list_symbols(scope) if s.name == "test_login")
    from code_graph_service.domain.enums import CallConfidence
    from code_graph_service.domain.models import GraphEdge

    store.put_edge(
        GraphEdge(
            id="edge:test-calls-login",
            scope=scope,
            rel_type=RelType.CALLS.value,
            source_id=test_fn.id,
            target_id=login.id,
            confidence=CallConfidence.EXACT,
            metadata={"provenance": "test"},
        )
    )
    overview = svc.architecture_overview(scope)
    hotspot_qns = {h["qualified_name"] for h in overview["knowledge_gaps"]["untested_hotspots"]}
    assert login.qualified_name not in hotspot_qns
