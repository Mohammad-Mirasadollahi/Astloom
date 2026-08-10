"""Tests for auto sync_repo policy and purge_scope."""

from __future__ import annotations

from pathlib import Path

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore


def _write_tree(root: Path, *, count: int = 2) -> None:
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (src / f"f{i}.py").write_text(f"def f{i}():\n    return {i}\n", encoding="utf-8")


def test_sync_empty_graph_is_full(tmp_path: Path):
    _write_tree(tmp_path)
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "p")
    result = service.sync_repo(
        scope,
        "tester",
        "corr-sync-1",
        "sync-key-1",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    assert result.mode == "full"
    assert result.files_ingested == 2
    assert len(service.store.list_symbols(scope)) >= 2


def test_sync_with_pending_is_incremental(tmp_path: Path):
    _write_tree(tmp_path, count=2)
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "p")
    service.sync_repo(
        scope,
        "tester",
        "corr-sync-seed",
        "sync-seed",
        {"root_path": str(tmp_path), "max_files": 1, "include_outcomes": True},
    )
    service.mark_file_pending("src/f1.py")
    result = service.sync_repo(
        scope,
        "tester",
        "corr-sync-2",
        "sync-key-2",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    assert result.mode == "incremental"
    assert result.files_discovered == 1
    assert result.files_ingested == 1


def test_sync_with_symbols_no_pending_is_incremental_walk(tmp_path: Path):
    _write_tree(tmp_path)
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "p")
    service.sync_repo(
        scope,
        "tester",
        "corr-a",
        "key-a",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    result = service.sync_repo(
        scope,
        "tester",
        "corr-b",
        "key-b",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    # Unchanged content → durable noop (hash-stable not enqueued; counted skipped).
    assert result.mode == "noop"
    assert result.files_discovered == 0
    assert result.files_ingested == 0
    assert result.files_skipped >= 2
    assert "no content changes" in (result.hint or "")


def test_sync_detects_content_change(tmp_path: Path):
    _write_tree(tmp_path, count=1)
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "p-change")
    service.sync_repo(
        scope,
        "tester",
        "corr-c1",
        "key-c1",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    (tmp_path / "src" / "f0.py").write_text("def f0():\n    return 99\n", encoding="utf-8")
    result = service.sync_repo(
        scope,
        "tester",
        "corr-c2",
        "key-c2",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    assert result.mode == "incremental"
    assert result.files_ingested == 1
    assert result.symbols_changed >= 1


def test_sync_truncated_hint_and_continue(tmp_path: Path):
    _write_tree(tmp_path, count=4)
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "p-trunc")
    first = service.sync_repo(
        scope,
        "tester",
        "corr-t1",
        "key-t1",
        {"root_path": str(tmp_path), "max_files": 2, "include_outcomes": True},
    )
    assert first.mode == "full"
    assert first.truncated is True
    assert "run sync again" in first.hint
    second = service.sync_repo(
        scope,
        "tester",
        "corr-t2",
        "key-t2",
        {"root_path": str(tmp_path), "max_files": 2, "include_outcomes": True},
    )
    assert second.mode == "incremental"
    # Continuation must index the previously skipped files, not only re-walk the first N.
    file_paths = {
        s.file_path
        for s in service.store.list_symbols(scope)
        if s.kind.value == "file" and s.file_path.startswith("src/")
    }
    assert file_paths == {"src/f0.py", "src/f1.py", "src/f2.py", "src/f3.py"}
    assert service.freshness_status(scope)["last_sync_at"]


def test_sync_unchanged_files_are_fast_noop(tmp_path: Path):
    _write_tree(tmp_path, count=2)
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "p-noop")
    service.sync_repo(
        scope,
        "tester",
        "corr-n1",
        "key-n1",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    again = service.sync_repo(
        scope,
        "tester",
        "corr-n2",
        "key-n2",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    assert again.mode == "noop"
    assert again.files_ingested == 0
    assert again.files_skipped >= 2


def test_ingest_backfills_missing_language(tmp_path: Path):
    src = tmp_path / "a.py"
    src.write_text("def hello():\n    return 1\n", encoding="utf-8")
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "p-lang-bf")
    service.ingest_file(
        scope,
        "tester",
        "c1",
        "k1",
        {"file_path": "a.py", "source": src.read_text(), "language": "python"},
    )
    # Simulate legacy rows without language.
    for sym in service.store.list_symbols(scope):
        sym.language = ""
        service.store.put_symbol(sym)
    service.ingest_file(
        scope,
        "tester",
        "c2",
        "k2",
        {"file_path": "a.py", "source": src.read_text(), "language": "python"},
    )
    assert all(
        s.language == "python"
        for s in service.store.list_symbols(scope)
        if s.kind.value != "unresolved"
    )


def test_ingest_persists_language(tmp_path: Path):
    src = tmp_path / "a.py"
    src.write_text("def hello():\n    return 1\n", encoding="utf-8")
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "p-lang")
    service.ingest_file(
        scope,
        "tester",
        "c",
        "k",
        {"file_path": "a.py", "source": src.read_text(), "language": "python"},
    )
    langs = {s.language for s in service.store.list_symbols(scope) if s.kind.value != "unresolved"}
    assert "python" in langs
    assert all(lang == "python" for lang in langs)


def test_purge_wipes_scope(tmp_path: Path):
    _write_tree(tmp_path)
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "p-purge")
    service.sync_repo(
        scope,
        "tester",
        "corr-p",
        "key-p",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    assert service.store.list_symbols(scope)
    service.mark_file_pending("src/f0.py")
    wiped = service.purge_scope(scope)
    assert wiped["ok"] is True
    assert wiped["symbols_after"] == 0
    assert wiped["edges_after"] == 0
    assert service.freshness_status()["pending_count"] == 0
    again = service.sync_repo(
        scope,
        "tester",
        "corr-p2",
        "key-p2",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    assert again.mode == "full"
