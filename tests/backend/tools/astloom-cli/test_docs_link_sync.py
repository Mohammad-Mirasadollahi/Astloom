"""Phase-2 docs link orchestrator (docs-sync + code-graph projection)."""

from __future__ import annotations

from pathlib import Path

import pytest

from astloom_cli.docs_link_sync import sync_human_docs
from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter, provisional_frontmatter
from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.locked_store import LockedStore
from code_graph_service.testing import InMemoryStore


SCOPE = Scope("t", "w", "docs-link")

AUTH_SOURCE = '''\
def login(user, password):
    return True
'''


LINKED_DOC = '''\
---
doc_id: doc-login-rules
title: Login rules
owner: platform
status: active
schema_version: "1.0"
linked_symbols:
  - src.auth.login
decision_refs: []
---

# Login rules

Human documentation for login.
'''


UNLINKED_DOC = '''\
---
doc_id: doc-overview
title: Overview
owner: platform
status: active
schema_version: "1.0"
linked_symbols: []
decision_refs: []
---

# Overview

No symbol links.
'''


@pytest.fixture(autouse=True)
def _isolated_docs_store(monkeypatch):
    """Keep unit docs-sync state local even when repository dotenv points at Postgres."""
    from docs_sync_service.core import DocsSyncService
    from docs_sync_service.testing import InMemoryStore as DocsStore

    service = DocsSyncService(DocsStore())
    monkeypatch.setattr(
        "astloom_cli.docs_link_sync._docs_sync_service",
        lambda: service,
    )
    return service


def test_parse_and_provisional_frontmatter():
    fm, body = parse_markdown_frontmatter(LINKED_DOC)
    assert fm["doc_id"] == "doc-login-rules"
    assert "Human documentation" in body
    filled = provisional_frontmatter("docs/x.md", "# Hello\n\nBody", {})
    assert filled["doc_id"].startswith("doc-")
    assert filled["title"] == "Hello"
    assert filled["linked_symbols"] == []


def test_resolve_docs_sync_database_url_falls_back_to_shared(monkeypatch):
    from astloom_cli.docs_link_sync import resolve_docs_sync_database_url

    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_DATABASE_URL", "postgresql://u:p@localhost:5432/astloom")
    assert resolve_docs_sync_database_url().startswith("postgresql://")
    monkeypatch.setenv(
        "ASTLOOM_DOCS_SYNC_DATABASE_URL",
        "postgresql://docs:x@localhost:5432/docs",
    )
    assert "docs" in resolve_docs_sync_database_url()


def test_resolve_docs_sync_database_url_from_compose(monkeypatch, tmp_path: Path):
    from astloom_cli.docs_link_sync import resolve_docs_sync_database_url

    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    monkeypatch.delenv("ASTLOOM_DATABASE_URL", raising=False)
    compose = tmp_path / "backend" / "deployments" / "compose"
    compose.mkdir(parents=True)
    (compose / ".env.local").write_text(
        "ASTLOOM_POSTGRES_USER=astloom\n"
        "ASTLOOM_POSTGRES_PASSWORD=secret\n"
        "ASTLOOM_POSTGRES_PORT=54329\n"
        "ASTLOOM_POSTGRES_DATABASE=astloom\n"
        "ASTLOOM_NEO4J_BOLT_PORT=7687\n"
        "ASTLOOM_NEO4J_PASSWORD=neo\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: tmp_path)
    url = resolve_docs_sync_database_url({})
    assert url == "postgresql://astloom:secret@127.0.0.1:54329/astloom"


def test_sync_human_docs_creates_anchor_and_edge(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "auth.py").write_text(AUTH_SOURCE, encoding="utf-8")
    (tmp_path / "docs" / "login.md").write_text(LINKED_DOC, encoding="utf-8")
    (tmp_path / "docs" / "overview.md").write_text(UNLINKED_DOC, encoding="utf-8")

    store = InMemoryStore()
    graph = CodeGraphService(store)
    graph.ingest_file(
        SCOPE,
        "test",
        "c1",
        "k1",
        {"file_path": "src/auth.py", "source": AUTH_SOURCE, "language": "python"},
    )

    from docs_sync_service.core import DocsSyncService, Scope as DocsScope
    from docs_sync_service.testing import InMemoryStore as DocsStore

    docs_service = DocsSyncService(DocsStore())
    monkeypatch.setattr("astloom_cli.docs_link_sync._docs_sync_service", lambda: docs_service)
    result = sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters={
            "docs_enabled": True,
            "doc_match_globs": ["**/*.md"],
            "doc_exclude_dirs": [],
            "doc_exclude_globs": [],
            "doc_paths": [],
            "max_files": 50,
        },
        actor="test",
        correlation_id="corr-1",
        repo_name="fixture",
    )
    assert result.docs_discovered == 2
    assert result.docs_indexed == 2
    assert result.links_created == 1
    assert result.anchors_registered == 1
    assert result.unresolved_tokens == []
    anchors = docs_service.store.list_anchors(DocsScope("t", "w", "docs-link"))
    assert len(anchors) == 1
    assert anchors[0].status == "synced"

    human_id = "doc:human:docs-link:doc-login-rules"
    human = store.get_symbol(human_id, SCOPE)
    login = store.get_symbol_by_qualified_name(SCOPE, "src.auth.login")
    assert login is not None
    edges = [
        e
        for e in store.list_edges(SCOPE)
        if e.rel_type == "DOCUMENTED_BY" and e.source_id == login.id and e.target_id == human.id
    ]
    assert len(edges) == 1

    # Unlinked overview still projected as a node, but no DOCUMENTED_BY from login to it.
    overview = store.get_symbol("doc:human:docs-link:doc-overview", SCOPE)
    assert overview is not None
    overview_edges = [e for e in store.list_edges(SCOPE) if e.target_id == overview.id and e.rel_type == "DOCUMENTED_BY"]
    assert overview_edges == []

    # Re-sync after editing the doc body must not ConflictError; stale links drop when tokens shrink.
    (tmp_path / "docs" / "login.md").write_text(
        LINKED_DOC.replace(
            "linked_symbols:\n  - src.auth.login\n",
            "linked_symbols: []\n",
        ).replace("Human documentation for login.", "Updated login docs."),
        encoding="utf-8",
    )
    again = sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters={
            "docs_enabled": True,
            "doc_match_globs": ["**/*.md"],
            "doc_exclude_dirs": [],
            "doc_exclude_globs": [],
            "doc_paths": [],
            "max_files": 50,
        },
        actor="test",
        correlation_id="corr-2",
        repo_name="fixture",
    )
    assert again.errors == []
    assert again.docs_indexed >= 1
    stale = [
        e
        for e in store.list_edges(SCOPE)
        if e.rel_type == "DOCUMENTED_BY" and e.source_id == login.id and e.target_id == human.id
    ]
    assert stale == []


def test_sync_human_docs_progress_only_counts_work_queue(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE", "0")
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "auth.py").write_text(AUTH_SOURCE, encoding="utf-8")
    (tmp_path / "docs" / "login.md").write_text(LINKED_DOC, encoding="utf-8")
    (tmp_path / "docs" / "overview.md").write_text(UNLINKED_DOC, encoding="utf-8")

    store = InMemoryStore()
    graph = CodeGraphService(store)
    graph.ingest_file(
        SCOPE,
        "test",
        "c1",
        "k1",
        {"file_path": "src/auth.py", "source": AUTH_SOURCE, "language": "python"},
    )
    sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters={
            "docs_enabled": True,
            "doc_match_globs": ["**/*.md"],
            "doc_exclude_dirs": [],
            "doc_exclude_globs": [],
            "doc_paths": [],
            "max_files": 50,
        },
        actor="test",
        correlation_id="corr-seed",
        repo_name="fixture",
    )
    (tmp_path / "docs" / "new.md").write_text(UNLINKED_DOC.replace("doc-overview", "doc-new"), encoding="utf-8")
    events: list[dict] = []
    result = sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters={
            "docs_enabled": True,
            "doc_match_globs": ["**/*.md"],
            "doc_exclude_dirs": [],
            "doc_exclude_globs": [],
            "doc_paths": [],
            "max_files": 50,
        },
        actor="test",
        correlation_id="corr-progress",
        repo_name="fixture",
        on_progress=events.append,
    )
    started = next(e for e in events if e.get("status") == "started")
    assert started["phase"] == "docs"
    assert started["queue_new"] == 1
    # overview + login are body-stable; without refresh_unchanged_links both drop.
    assert started["queue_unchanged"] == 0
    assert started["total"] == 1
    finished = next(e for e in events if e.get("status") == "finished")
    assert finished["done"] == finished["total"] == 1
    assert result.docs_indexed == 1


def test_sync_human_docs_runs_with_parallel_workers(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE", "0")
    monkeypatch.setenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", "4")
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "auth.py").write_text(AUTH_SOURCE, encoding="utf-8")
    for i in range(8):
        body = UNLINKED_DOC.replace("doc-overview", f"doc-{i}").replace("Overview", f"Doc {i}")
        (tmp_path / "docs" / f"d{i}.md").write_text(body, encoding="utf-8")
    (tmp_path / "docs" / "login.md").write_text(LINKED_DOC, encoding="utf-8")

    import threading
    import time

    from astloom_cli.process_containers import clear_process_containers
    from docs_sync_service.core import DocsSyncService
    from docs_sync_service.testing import InMemoryStore as DocsInMemoryStore

    class OverlapProbeStore(DocsInMemoryStore):
        """Record concurrent entry into put_document (proves no CLI docs_lock)."""

        def __init__(self) -> None:
            super().__init__()
            self.max_overlap = 0
            self.close_calls = 0
            self._inflight = 0
            self._probe = threading.Lock()

        def put_document(self, document):  # noqa: ANN001
            with self._probe:
                self._inflight += 1
                self.max_overlap = max(self.max_overlap, self._inflight)
            try:
                time.sleep(0.03)
                return super().put_document(document)
            finally:
                with self._probe:
                    self._inflight -= 1

        def close(self) -> None:
            self.close_calls += 1

    class ResetProbeStore(InMemoryStore):
        def __init__(self) -> None:
            super().__init__()
            self.reset_calls = 0

        def reset_connections(self) -> None:
            self.reset_calls += 1

    clear_process_containers()
    probe = OverlapProbeStore()
    monkeypatch.setattr(
        "astloom_cli.docs_link_sync._docs_sync_service",
        lambda: DocsSyncService(probe),
    )

    store = ResetProbeStore()
    graph = CodeGraphService(LockedStore(store, lock_reads=True))
    graph.ingest_file(
        SCOPE,
        "test",
        "c1",
        "k1",
        {"file_path": "src/auth.py", "source": AUTH_SOURCE, "language": "python"},
    )
    events: list[dict] = []
    result = sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters={
            "docs_enabled": True,
            "doc_match_globs": ["**/*.md"],
            "doc_exclude_dirs": [],
            "doc_exclude_globs": [],
            "doc_paths": [],
            "max_files": 50,
        },
        actor="test",
        correlation_id="corr-parallel",
        repo_name="fixture",
        on_progress=events.append,
    )
    started = next(e for e in events if e.get("status") == "started")
    assert started["file_workers"] == 4
    assert result.docs_indexed == 9
    assert result.anchors_registered >= 1
    # At least one progress snap should report concurrent in-flight under workers>1.
    assert any(int(e.get("files_in_flight") or 0) >= 1 for e in events if e.get("status") == "active")
    # Docs-sync writes must overlap across workers (not CLI single-flight).
    assert probe.max_overlap >= 2
    assert probe.close_calls == 1
    assert store.reset_calls == 1
    clear_process_containers()


def test_sync_human_docs_caps_workers_to_database_slots(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE", "0")
    monkeypatch.setenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", "29")
    (tmp_path / "docs").mkdir()
    for i in range(12):
        body = UNLINKED_DOC.replace("doc-overview", f"doc-{i}").replace("Overview", f"Doc {i}")
        (tmp_path / "docs" / f"d{i}.md").write_text(body, encoding="utf-8")

    from docs_sync_service.core import DocsSyncService
    from docs_sync_service.testing import InMemoryStore as DocsInMemoryStore

    monkeypatch.setattr(
        "astloom_cli.docs_link_sync._docs_sync_service",
        lambda: DocsSyncService(DocsInMemoryStore()),
    )
    events: list[dict] = []
    result = sync_human_docs(
        graph_service=CodeGraphService(InMemoryStore()),
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters={
            "docs_enabled": True,
            "doc_match_globs": ["**/*.md"],
            "doc_exclude_dirs": [],
            "doc_exclude_globs": [],
            "doc_paths": [],
            "max_files": 50,
        },
        actor="test",
        correlation_id="corr-db-slots",
        repo_name="fixture",
        on_progress=events.append,
    )

    started = next(e for e in events if e.get("status") == "started")
    assert started["file_workers"] == 8
    assert result.docs_indexed == 12


def test_sync_human_docs_skips_unchanged_unlinked(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE", "0")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "overview.md").write_text(UNLINKED_DOC, encoding="utf-8")

    store = InMemoryStore()
    graph = CodeGraphService(store)
    filters = {
        "docs_enabled": True,
        "doc_match_globs": ["**/*.md"],
        "doc_exclude_dirs": [],
        "doc_exclude_globs": [],
        "doc_paths": [],
        "max_files": 50,
    }
    first = sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters=filters,
        actor="test",
        correlation_id="corr-a",
        repo_name="fixture",
    )
    assert first.docs_indexed == 1
    second = sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters=filters,
        actor="test",
        correlation_id="corr-b",
        repo_name="fixture",
    )
    assert second.docs_discovered == 1
    assert second.docs_indexed == 0


def test_resolve_sync_filters_docs_vs_code(tmp_path: Path, monkeypatch):
    from astloom_cli.sync_config import resolve_sync_filters

    monkeypatch.delenv("ASTLOOM_SYNC_DOC_PATHS", raising=False)
    monkeypatch.delenv("ASTLOOM_SYNC_DOC_MATCH", raising=False)
    monkeypatch.delenv("ASTLOOM_SYNC_EXCLUDE_DIRS", raising=False)
    (tmp_path / "astloom.sync.yaml").write_text(
        "\n".join(
            [
                "code:",
                "  exclude:",
                "    - tests",
                "docs:",
                "  match:",
                "    - '**/*.md'",
                "  exclude:",
                "    - '**/CHANGELOG.md'",
                "",
            ]
        ),
        encoding="utf-8",
    )
    filters = resolve_sync_filters(root=tmp_path)
    assert "tests" in filters["exclude_dirs"]
    assert "docs" not in filters["exclude_dirs"]  # code exclude must not require docs
    assert filters["docs_enabled"] is True
    assert "**/*.md" in filters["doc_match_globs"]
    assert "**/CHANGELOG.md" in filters["doc_exclude_globs"]
    assert filters["include_paths"] == []

    (tmp_path / "astloom.sync.yaml").write_text(
        "code:\n  exclude: []\ndocs:\n  match: []\n",
        encoding="utf-8",
    )
    filters2 = resolve_sync_filters(root=tmp_path)
    assert filters2["docs_enabled"] is False
    assert filters2["doc_match_globs"] == []

    # Legacy: bare exclude still defaults docs to **/*.md
    (tmp_path / "astloom.sync.yaml").write_text("exclude: []\n", encoding="utf-8")
    filters3 = resolve_sync_filters(root=tmp_path)
    assert filters3["docs_enabled"] is True
    assert "**/*.md" in filters3["doc_match_globs"]


AUTH_BACKEND = '''\
def login(user, password):
    return True
'''


EVIDENCE_DOC = '''\
---
doc_id: doc-evidence-login
title: Evidence login
owner: platform
status: active
schema_version: "1.0"
linked_symbols: []
decision_refs: []
lifecycle_lane: current
---

# Evidence login

See `backend/pkg/auth.py` for the login helper.
'''


PLAIN_DOC = '''\
---
doc_id: doc-plain
title: Plain
owner: platform
status: active
schema_version: "1.0"
linked_symbols: []
decision_refs: []
lifecycle_lane: archive
---

# Plain

No code citations.
'''


def test_sync_human_docs_merges_evidence_and_creates_edge(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE", "1")
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE_APPLY", "1")
    (tmp_path / "backend" / "pkg").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "backend" / "pkg" / "auth.py").write_text(AUTH_BACKEND, encoding="utf-8")
    (tmp_path / "docs" / "evidence.md").write_text(EVIDENCE_DOC, encoding="utf-8")
    (tmp_path / "docs" / "plain.md").write_text(PLAIN_DOC, encoding="utf-8")

    store = InMemoryStore()
    graph = CodeGraphService(store)
    graph.ingest_file(
        SCOPE,
        "test",
        "c1",
        "k1",
        {"file_path": "backend/pkg/auth.py", "source": AUTH_BACKEND, "language": "python"},
    )

    result = sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters={
            "docs_enabled": True,
            "doc_match_globs": ["**/*.md"],
            "doc_exclude_dirs": [],
            "doc_exclude_globs": [],
            "doc_paths": [],
            "max_files": 50,
        },
        actor="test",
        correlation_id="corr-ev",
        repo_name="fixture",
    )
    assert result.errors == []
    assert result.evidence_enabled is True
    assert result.evidence_tokens_new >= 1
    assert result.evidence_frontmatter_applied >= 1
    assert result.links_created >= 1

    fm, _body = parse_markdown_frontmatter(
        (tmp_path / "docs" / "evidence.md").read_text(encoding="utf-8")
    )
    assert "backend/pkg/auth.py::login" in (fm.get("linked_symbols") or [])

    login = store.get_symbol_by_qualified_name(SCOPE, "backend.pkg.auth.login")
    assert login is not None
    human = store.get_symbol("doc:human:docs-link:doc-evidence-login", SCOPE)
    edges = [
        e
        for e in store.list_edges(SCOPE)
        if e.rel_type == "DOCUMENTED_BY" and e.source_id == login.id and e.target_id == human.id
    ]
    assert len(edges) == 1


def test_sync_human_docs_evidence_can_disable(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE", "0")
    (tmp_path / "backend" / "pkg").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "backend" / "pkg" / "auth.py").write_text(AUTH_BACKEND, encoding="utf-8")
    (tmp_path / "docs" / "evidence.md").write_text(EVIDENCE_DOC, encoding="utf-8")

    store = InMemoryStore()
    graph = CodeGraphService(store)
    graph.ingest_file(
        SCOPE,
        "test",
        "c1",
        "k1",
        {"file_path": "backend/pkg/auth.py", "source": AUTH_BACKEND, "language": "python"},
    )
    result = sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters={
            "docs_enabled": True,
            "doc_match_globs": ["**/*.md"],
            "doc_exclude_dirs": [],
            "doc_exclude_globs": [],
            "doc_paths": [],
            "max_files": 50,
        },
        actor="test",
        correlation_id="corr-off",
        repo_name="fixture",
    )
    assert result.evidence_enabled is False
    assert result.evidence_tokens_new == 0
    assert result.links_created == 0
    fm, _ = parse_markdown_frontmatter(
        (tmp_path / "docs" / "evidence.md").read_text(encoding="utf-8")
    )
    assert (fm.get("linked_symbols") or []) == []


def test_phase2_priority_orders_evidence_first(tmp_path: Path, monkeypatch):
    from astloom_cli.docs_link_sync import _phase2_priority

    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE", "1")
    (tmp_path / "backend" / "pkg").mkdir(parents=True)
    (tmp_path / "backend" / "pkg" / "auth.py").write_text(AUTH_BACKEND, encoding="utf-8")
    ev = _phase2_priority(
        rel="docs/a.md",
        body='See `backend/pkg/auth.py`.\n',
        frontmatter={"lifecycle_lane": "archive", "linked_symbols": []},
        catalog_row=None,
        root_path=tmp_path,
        evidence_enabled=True,
    )
    plain = _phase2_priority(
        rel="docs/b.md",
        body="No paths.\n",
        frontmatter={"lifecycle_lane": "current", "linked_symbols": []},
        catalog_row={"lifecycle_lane": "current"},
        root_path=tmp_path,
        evidence_enabled=True,
    )
    assert ev < plain


def test_sync_skips_when_stale_duplicate_human_hash_last(tmp_path: Path, monkeypatch):
    """Regression: path with provisional + stable doc symbols must not re-queue as changed."""
    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE", "0")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "overview.md").write_text(UNLINKED_DOC, encoding="utf-8")

    store = InMemoryStore()
    graph = CodeGraphService(store)
    filters = {
        "docs_enabled": True,
        "doc_match_globs": ["**/*.md"],
        "doc_exclude_dirs": [],
        "doc_exclude_globs": [],
        "doc_paths": [],
        "max_files": 50,
    }
    sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters=filters,
        actor="test",
        correlation_id="corr-seed",
        repo_name="fixture",
    )
    # Simulate remediator renaming doc_id: leave stale symbol, add current one.
    from code_graph_service.domain.enums import DocStatus, SymbolKind
    from code_graph_service.domain.hashing import digest
    from code_graph_service.domain.models import GraphSymbol
    from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter

    text = (tmp_path / "docs" / "overview.md").read_text(encoding="utf-8")
    _, body = parse_markdown_frontmatter(text)
    body_hash = digest(body)
    current = store.get_symbol("doc:human:docs-link:doc-overview", SCOPE)
    assert current is not None
    assert current.hash_value == body_hash
    store.put_symbol(
        GraphSymbol(
            id="doc:human:docs-link:doc-stale-orphan",
            scope=SCOPE,
            kind=SymbolKind.DOCUMENTATION,
            file_path="docs/overview.md",
            name="overview.md",
            qualified_name="human:doc-stale-orphan",
            signature="stale",
            body="old body",
            hash_value=digest("old body"),
            ai_documentation="",
            doc_status=DocStatus.HUMAN,
            embedding=[],
            version=1,
            created_at=current.created_at,
            updated_at=current.updated_at,
            language="",
        )
    )
    events: list[dict] = []
    again = sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters=filters,
        actor="test",
        correlation_id="corr-dup",
        repo_name="fixture",
        on_progress=events.append,
    )
    started = next(e for e in events if e.get("status") == "started")
    assert started["queue_new"] == 0
    assert started["queue_changed"] == 0
    assert started["total"] == 0
    assert again.docs_indexed == 0


def test_sync_refresh_unchanged_links_requeues_linked(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE", "0")
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "auth.py").write_text(AUTH_SOURCE, encoding="utf-8")
    (tmp_path / "docs" / "login.md").write_text(LINKED_DOC, encoding="utf-8")
    (tmp_path / "docs" / "overview.md").write_text(UNLINKED_DOC, encoding="utf-8")

    store = InMemoryStore()
    graph = CodeGraphService(store)
    graph.ingest_file(
        SCOPE,
        "test",
        "c1",
        "k1",
        {"file_path": "src/auth.py", "source": AUTH_SOURCE, "language": "python"},
    )
    filters = {
        "docs_enabled": True,
        "doc_match_globs": ["**/*.md"],
        "doc_exclude_dirs": [],
        "doc_exclude_globs": [],
        "doc_paths": [],
        "max_files": 50,
    }
    sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters=filters,
        actor="test",
        correlation_id="corr-seed",
        repo_name="fixture",
    )
    events: list[dict] = []
    sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters=filters,
        actor="test",
        correlation_id="corr-refresh",
        repo_name="fixture",
        on_progress=events.append,
        refresh_unchanged_links=True,
    )
    started = next(e for e in events if e.get("status") == "started")
    assert started["queue_unchanged"] == 1
    assert started["total"] == 1


def test_sync_retires_stale_human_doc_symbol_for_path(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DOCS_SYNC_DATABASE_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE", "0")
    (tmp_path / "docs").mkdir()
    # Body-tier provisional id first.
    body_tier = UNLINKED_DOC.replace("doc_id: doc-overview\n", "")
    (tmp_path / "docs" / "overview.md").write_text(body_tier, encoding="utf-8")

    store = InMemoryStore()
    graph = CodeGraphService(store)
    filters = {
        "docs_enabled": True,
        "doc_match_globs": ["**/*.md"],
        "doc_exclude_dirs": [],
        "doc_exclude_globs": [],
        "doc_paths": [],
        "max_files": 50,
    }
    sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters=filters,
        actor="test",
        correlation_id="corr-a",
        repo_name="fixture",
    )
    provisional_ids = [
        s.id
        for s in store.list_symbols(SCOPE)
        if str(s.file_path) == "docs/overview.md"
    ]
    assert len(provisional_ids) == 1
    # Upgrade to stable doc_id (remediate) — must retire provisional symbol.
    (tmp_path / "docs" / "overview.md").write_text(UNLINKED_DOC, encoding="utf-8")
    sync_human_docs(
        graph_service=graph,
        graph_scope=SCOPE,
        root_path=tmp_path,
        filters=filters,
        actor="test",
        correlation_id="corr-b",
        repo_name="fixture",
    )
    remaining = [
        s.id
        for s in store.list_symbols(SCOPE)
        if str(s.file_path) == "docs/overview.md"
    ]
    assert remaining == ["doc:human:docs-link:doc-overview"]
    assert provisional_ids[0] not in remaining
