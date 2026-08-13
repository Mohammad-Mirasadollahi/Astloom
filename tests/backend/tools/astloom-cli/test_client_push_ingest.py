"""Tests for client content-push ingest (no on-server tree)."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.enums import SymbolKind
from code_graph_service.domain.hashing import content_hash
from code_graph_service.testing import InMemoryStore

from astloom_cli.connect_flow.client_push import build_push_files


def test_ingest_pushed_sources_progress_includes_file_workers():
    """Client sync UI needs file_workers so it does not print '? workers'."""
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "push-workers")
    events: list[dict] = []
    service.ingest_pushed_sources(
        scope,
        "tester",
        "corr-workers",
        "push-key-workers",
        {
            "files": [
                {
                    "file_path": "src/a.py",
                    "source": "def alpha():\n    return 1\n",
                    "language": "python",
                }
            ],
            "present_paths": ["src/a.py"],
            "include_outcomes": True,
            "on_progress": events.append,
        },
    )
    assert events
    ingest_events = [
        e
        for e in events
        if e.get("phase") == "ingest"
        and str(e.get("status") or "") in {"started", "active", "ok", "unchanged", "failed", "skipped"}
    ]
    assert ingest_events
    assert all(int(e.get("file_workers") or 0) >= 1 for e in ingest_events)


def test_ingest_pushed_sources_indexes_without_disk_root():
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "push")
    result = service.ingest_pushed_sources(
        scope,
        "tester",
        "corr-1",
        "push-key-1",
        {
            "files": [
                {
                    "file_path": "src/a.py",
                    "source": "def alpha():\n    return 1\n",
                    "language": "python",
                }
            ],
            "present_paths": ["src/a.py"],
            "include_outcomes": True,
        },
    )
    assert result.files_ingested == 1
    assert result.files_failed == 0
    names = {s.name for s in service.store.list_symbols(scope)}
    assert "alpha" in names


def test_ingest_pushed_sources_prunes_missing_present_paths():
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "prune")
    service.ingest_pushed_sources(
        scope,
        "tester",
        "corr-1",
        "push-key-1",
        {
            "files": [
                {"file_path": "a.py", "source": "def a():\n    return 1\n", "language": "python"},
                {"file_path": "b.py", "source": "def b():\n    return 2\n", "language": "python"},
            ],
            "present_paths": ["a.py", "b.py"],
            "inventory_complete": True,
        },
    )
    service.ingest_pushed_sources(
        scope,
        "tester",
        "corr-2",
        "push-key-2",
        {
            "files": [],
            "present_paths": ["a.py"],
            "inventory_complete": True,
        },
    )
    files = {
        s.file_path
        for s in service.store.list_symbols(scope)
        if s.kind == SymbolKind.FILE
    }
    assert files == {"a.py"}


def test_ingest_pushed_sources_ignores_present_paths_without_inventory_complete():
    """Root cause guard: partial present_paths must not wipe the graph."""
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "no-prune")
    service.ingest_pushed_sources(
        scope,
        "tester",
        "corr-1",
        "push-key-1",
        {
            "files": [
                {"file_path": "a.py", "source": "def a():\n    return 1\n", "language": "python"},
                {"file_path": "b.py", "source": "def b():\n    return 2\n", "language": "python"},
            ],
            "present_paths": ["a.py", "b.py"],
            "inventory_complete": True,
        },
    )
    service.ingest_pushed_sources(
        scope,
        "tester",
        "corr-2",
        "push-key-2",
        {
            "files": [],
            # Legacy / scoped client mistake: subset without completeness flag.
            "present_paths": ["a.py"],
        },
    )
    files = {
        s.file_path
        for s in service.store.list_symbols(scope)
        if s.kind == SymbolKind.FILE
    }
    assert files == {"a.py", "b.py"}


def test_build_push_files_skips_unchanged_hashes(tmp_path: Path):
    (tmp_path / "astloom.sync.yaml").write_text(
        "exclude_dirs: []\ninclude_extensions: [.py]\n",
        encoding="utf-8",
    )
    src = tmp_path / "src"
    src.mkdir()
    body = "def alpha():\n    return 1\n"
    (src / "a.py").write_text(body, encoding="utf-8")
    digest = content_hash(body, "python")["hash"]
    args = Namespace(
        exclude_dir=[],
        include_path=[],
        include_ext=[],
        max_files=50,
    )
    files, present, skipped, prune_ok = build_push_files(
        tmp_path,
        args,
        remote_hashes={"src/a.py": digest},
    )
    assert present == ["src/a.py"]
    assert files == []
    assert skipped == 1
    assert prune_ok is True

    files2, _, skipped2, prune_ok2 = build_push_files(tmp_path, args, remote_hashes={})
    assert len(files2) == 1
    assert files2[0]["file_path"] == "src/a.py"
    assert skipped2 == 0
    assert prune_ok2 is True


def test_ingest_pushed_sources_rejects_path_traversal():
    from code_graph_service.domain.errors import ValidationError

    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "sec")
    try:
        service.ingest_pushed_sources(
            scope,
            "tester",
            "corr",
            "key",
            {
                "files": [
                    {
                        "file_path": "../etc/passwd",
                        "source": "x = 1\n",
                        "language": "python",
                    }
                ],
            },
        )
        raised = False
    except ValidationError:
        raised = True
    assert raised


def test_ingest_pushed_sources_rejects_absolute_path():
    from code_graph_service.domain.errors import ValidationError

    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "sec2")
    try:
        service.ingest_pushed_sources(
            scope,
            "tester",
            "corr",
            "key",
            {"files": [{"file_path": "/tmp/x.py", "source": "x=1\n", "language": "python"}]},
        )
        raised = False
    except ValidationError:
        raised = True
    assert raised


def test_ingest_pushed_sources_soft_fails_oversize_body():
    service = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "sec3")
    big = "x" * 5000
    result = service.ingest_pushed_sources(
        scope,
        "tester",
        "corr",
        "key",
        {
            "files": [{"file_path": "a.py", "source": big, "language": "python"}],
            "max_file_bytes": 1024,
            "include_outcomes": True,
        },
    )
    assert result.files_ingested == 0
    assert result.files_failed == 1


def test_run_ingest_push_uses_http(monkeypatch):
    """Content-push always uses HTTP when graph_url + token are set (SSH removed)."""
    from astloom_cli.connect_config import ConnectSettings
    from astloom_cli.connect_flow import client_push as cp

    seen: list[str] = []

    def fake_http(settings, args, body, **_kwargs):
        seen.append("http")
        return {"files_ingested": 0, "files_failed": 0}

    monkeypatch.setattr(cp, "_run_ingest_push_http", fake_http)
    settings = ConnectSettings(
        graph_url="http://g.internal:8080",
        api_token="tokentokentoken12",
    )
    out = cp._run_ingest_push(settings, Namespace(sync_mode=""), {"files": []})
    assert seen == ["http"]
    assert out["files_failed"] == 0


def test_run_ingest_push_without_graph_url_exits_with_hint():
    """No graph_url → clear SystemExit, never a silent push."""
    from astloom_cli.connect_config import ConnectSettings
    from astloom_cli.connect_flow import client_push as cp

    settings = ConnectSettings(graph_url="", api_token="")
    with pytest.raises(SystemExit, match="graph_url"):
        cp._run_ingest_push(settings, Namespace(sync_mode=""), {"files": []})


def test_run_ingest_push_http_consumes_ndjson(monkeypatch):
    """HTTP path requests NDJSON (Accept header) and feeds progress to the caller."""
    import sys
    from types import ModuleType

    from astloom_cli.connect_config import ConnectSettings
    from astloom_cli.connect_flow import client_push as cp

    calls: dict = {}

    class Resp:
        status_code = 200
        headers: dict = {}

        def iter_lines(self):
            yield '{"type":"progress","phase":"ingest","done":1,"total":1,"file":"a.py"}'
            yield '{"type":"result","files_ingested":1,"files_failed":0}'

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def stream(method, url, *, headers=None, json=None, timeout=None, verify=None):
        calls["method"] = method
        calls["url"] = url
        calls["headers"] = dict(headers or {})
        calls["timeout"] = timeout
        return Resp()

    fake = ModuleType("httpx")
    fake.HTTPError = Exception
    fake.Timeout = __import__("httpx").Timeout
    fake.stream = stream
    monkeypatch.setitem(sys.modules, "httpx", fake)
    monkeypatch.setattr(cp, "httpx_verify", lambda _settings: True)

    seen: list[dict] = []
    settings = ConnectSettings(
        graph_url="https://example.test",
        api_token="tok",
        tenant="t",
        workspace="w",
        project="p",
    )
    out = cp._run_ingest_push_http(
        settings,
        Namespace(project="p", sync_mode=""),
        {"files": []},
        on_progress=lambda e: seen.append(e),
    )
    assert out["files_ingested"] == 1
    assert calls["method"] == "POST"
    assert calls["headers"].get("Accept") == "application/x-ndjson"
    # Defense in depth for proxies that strip Accept.
    assert calls["url"].endswith("/graph/ingest-push?stream=1")
    assert seen and seen[0]["done"] == 1
    timeout = calls["timeout"]
    assert timeout is not None
    assert float(timeout.connect) == 30.0
    assert float(timeout.read) == 600.0


def test_run_ingest_push_http_compat_plain_json(monkeypatch):
    """Old server returning a plain JSON body (no NDJSON) is parsed once."""
    import sys
    from types import ModuleType

    from astloom_cli.connect_config import ConnectSettings
    from astloom_cli.connect_flow import client_push as cp

    class Resp:
        status_code = 200
        headers = {"content-type": "application/json"}

        def read(self):
            return None

        def json(self):
            return {"files_ingested": 2, "files_failed": 0}

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    fake = ModuleType("httpx")
    fake.HTTPError = Exception
    fake.Timeout = __import__("httpx").Timeout
    fake.stream = lambda method, url, **_kw: Resp()
    monkeypatch.setitem(sys.modules, "httpx", fake)
    monkeypatch.setattr(cp, "httpx_verify", lambda _settings: True)

    settings = ConnectSettings(
        graph_url="https://example.test", api_token="tok", tenant="t", workspace="w", project="p"
    )
    out = cp._run_ingest_push_http(settings, Namespace(project="p", sync_mode=""), {"files": []})
    assert out == {"files_ingested": 2, "files_failed": 0}


def test_client_push_sync_without_graph_url_exits_with_https_hint(tmp_path: Path):
    """client_push_sync must fail closed (mentioning graph_url/HTTPS)."""
    from astloom_cli.connect_config import ConnectSettings
    from astloom_cli.connect_flow.client_push import client_push_sync

    settings = ConnectSettings(graph_url="", api_token="", tenant="t", workspace="w", project="p")
    with pytest.raises(SystemExit, match="graph_url"):
        client_push_sync(settings, Namespace(), work=tmp_path)


def test_client_push_sync_no_transport_exits_with_https_hint(tmp_path: Path):
    from astloom_cli.connect_config import ConnectSettings
    from astloom_cli.connect_flow.client_push import client_push_sync

    settings = ConnectSettings(graph_url="", api_token="")
    with pytest.raises(SystemExit, match="HTTPS"):
        client_push_sync(settings, Namespace(), work=tmp_path)


def test_client_push_sync_stream_failure_marks_run_not_finished(monkeypatch, tmp_path: Path, capsys):
    """A failing push must not print a green finished/100% tracker block."""
    import astloom_cli.sync_progress as sync_progress
    from astloom_cli.commands import graph as graph_cmd
    from astloom_cli.connect_config import ConnectSettings
    from astloom_cli.connect_flow import client_push as cp

    finishes: list[bool] = []

    class _Tracker:
        def __init__(self, **_kwargs):
            pass

        def __call__(self, _event):
            pass

        def begin_phase(self):
            pass

        def finish(self, *, cancelled: bool = False):
            finishes.append(cancelled)

    monkeypatch.setattr(sync_progress, "SyncProgressTracker", _Tracker)
    monkeypatch.setattr(graph_cmd, "_require_cloud_llm_consent", lambda *a, **k: None)
    monkeypatch.setattr(cp, "fetch_remote_file_hashes", lambda *a, **k: {})
    monkeypatch.setattr(cp, "build_push_files", lambda *a, **k: ([], [], 0, True))
    monkeypatch.setattr(cp, "build_push_docs", lambda *a, **k: [])

    def boom(*_a, **_k):
        raise SystemExit("error: ingest-push stream: boom")

    monkeypatch.setattr(cp, "_run_ingest_push", boom)

    settings = ConnectSettings(
        graph_url="https://g.example",
        api_token="tokentokentoken12",
        tenant="t",
        workspace="w",
        project="p",
    )
    args = Namespace(project="p", sync_mode="", progress_interval=30)
    with pytest.raises(SystemExit, match="ingest-push stream"):
        cp.client_push_sync(settings, args, work=tmp_path)
    assert finishes == [True]
    # Empty remote hashes while graph is ready must surface a skip-disabled warning.
    assert any("remote file-hashes empty" in line for line in (capsys.readouterr().out.splitlines()))


def test_client_push_sync_note_shows_remote_hashes_and_batch_total(tmp_path: Path, monkeypatch, capsys):
    from argparse import Namespace

    from astloom_cli import sync_progress
    from astloom_cli.commands import graph as graph_cmd
    from astloom_cli.connect_config import ConnectSettings
    from astloom_cli.connect_flow import client_push as cp

    monkeypatch.setattr(graph_cmd, "_require_cloud_llm_consent", lambda *a, **k: None)
    monkeypatch.setattr(cp, "fetch_remote_file_hashes", lambda *a, **k: {"a.py": "h1"})
    monkeypatch.setattr(
        cp,
        "build_push_files",
        lambda *a, **k: (
            [{"file_path": "a.py", "source": "x=1\n", "language": "python"}],
            ["a.py"],
            0,
            True,
        ),
    )
    monkeypatch.setattr(cp, "build_push_docs", lambda *a, **k: [])
    monkeypatch.setattr(cp, "_run_ingest_push", lambda *a, **k: {"files_ingested": 1, "files_failed": 0})

    class _Tracker:
        def __init__(self, **_kwargs):
            pass

        def __call__(self, _event):
            pass

        def begin_phase(self):
            pass

        def finish(self, *, cancelled: bool = False):
            pass

    monkeypatch.setattr(sync_progress, "SyncProgressTracker", _Tracker)
    settings = ConnectSettings(
        graph_url="https://g.example",
        api_token="tokentokentoken12",
        tenant="t",
        workspace="w",
        project="p",
    )
    assert (
        cp.client_push_sync(settings, Namespace(project="p", sync_mode="", progress_interval=30), work=tmp_path)
        == 0
    )
    out = capsys.readouterr().out
    assert "remote_hashes=1" in out
    assert "batches=1" in out
    assert "push batch 1/1" in out
    assert "prune=on" in out


def test_build_push_files_prune_ok_false_when_include_path(tmp_path: Path):
    from astloom_cli.connect_flow.client_push import build_push_files

    (tmp_path / "astloom.sync.yaml").write_text(
        "code:\n  exclude: []\n",
        encoding="utf-8",
    )
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("x=1\n", encoding="utf-8")
    args = Namespace(exclude_dir=[], include_path=["pkg"], include_ext=[".py"], max_files=50)
    _files, _present, _skipped, prune_ok = build_push_files(tmp_path, args, remote_hashes={})
    assert prune_ok is False


def test_build_push_files_prune_ok_false_when_max_files_truncates(tmp_path: Path):
    from astloom_cli.connect_flow.client_push import build_push_files

    (tmp_path / "astloom.sync.yaml").write_text(
        "code:\n  exclude: []\n",
        encoding="utf-8",
    )
    src = tmp_path / "src"
    src.mkdir()
    for i in range(5):
        (src / f"f{i}.py").write_text(f"x={i}\n", encoding="utf-8")
    args = Namespace(exclude_dir=[], include_path=[], include_ext=[".py"], max_files=3)
    files, present, _skipped, prune_ok = build_push_files(tmp_path, args, remote_hashes={})
    assert len(present) == 3
    assert len(files) == 3
    assert prune_ok is False


def test_batches_omits_present_paths_when_not_authoritative():
    from astloom_cli.connect_flow.client_push import _batches

    batches = _batches(
        [{"file_path": "a.py", "source": "x=1\n", "language": "python"}],
        ["a.py", "b.py"],
        include_present_paths=False,
    )
    assert len(batches) == 1
    assert "present_paths" not in batches[0]
    assert "inventory_complete" not in batches[0]


def test_batches_sets_inventory_complete_when_authoritative():
    from astloom_cli.connect_flow.client_push import _batches
    from astloom_cli.parser._core import HARD_SYNC_MAX_FILES

    batches = _batches(
        [{"file_path": "a.py", "source": "x=1\n", "language": "python"}],
        ["a.py"],
        include_present_paths=True,
    )
    assert batches[0]["present_paths"] == ["a.py"]
    assert batches[0]["inventory_complete"] is True
    assert batches[0]["max_files"] == HARD_SYNC_MAX_FILES


def test_resolve_discovery_max_files_auto_vs_explicit():
    from astloom_cli.parser._core import HARD_SYNC_MAX_FILES, resolve_discovery_max_files

    assert resolve_discovery_max_files(0) == HARD_SYNC_MAX_FILES
    assert resolve_discovery_max_files(None) == HARD_SYNC_MAX_FILES
    assert resolve_discovery_max_files(50) == 50
    assert resolve_discovery_max_files(99_999) == HARD_SYNC_MAX_FILES


def test_build_push_files_auto_discovers_beyond_legacy_2000(tmp_path: Path):
    from astloom_cli.connect_flow.client_push import build_push_files
    from astloom_cli.parser._core import DEFAULT_SYNC_MAX_FILES

    (tmp_path / "astloom.sync.yaml").write_text("code:\n  exclude: []\n", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    for i in range(25):
        (src / f"f{i:02d}.py").write_text(f"x={i}\n", encoding="utf-8")
    args = Namespace(
        exclude_dir=[],
        include_path=[],
        include_ext=[".py"],
        max_files=DEFAULT_SYNC_MAX_FILES,  # auto
    )
    files, present, _skipped, prune_ok = build_push_files(tmp_path, args, remote_hashes={})
    assert len(present) == 25
    assert len(files) == 25
    assert prune_ok is True


def test_build_push_docs_includes_frontmatter_doc(tmp_path: Path):
    from astloom_cli.connect_flow.client_push import _batches, build_push_docs

    (tmp_path / "astloom.sync.yaml").write_text(
        "code:\n  exclude: []\ndocs:\n  match:\n    - '**/*.md'\n  exclude: []\n",
        encoding="utf-8",
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "note.md").write_text(
        "---\n"
        "doc_id: as.doc.test.note\n"
        "title: Note\n"
        "doc_type: note\n"
        "status: active\n"
        "schema_version: '1.0'\n"
        "owner: tests\n"
        "summary: test\n"
        "tags: [test]\n"
        "phase: test\n"
        "canonical_path: docs/note.md\n"
        "---\n"
        "\n"
        "# Note\n",
        encoding="utf-8",
    )
    args = Namespace(exclude_dir=[], include_path=[], include_ext=[], max_files=50)
    docs = build_push_docs(tmp_path, args)
    assert any(d["doc_id"] == "as.doc.test.note" for d in docs)
    batches = _batches([], ["src/a.py"], docs=docs)
    assert len(batches) == 1
    assert batches[0]["docs"]
    assert batches[0]["present_paths"] == ["src/a.py"]


def test_build_push_docs_honors_include_path(tmp_path: Path):
    from astloom_cli.connect_flow.client_push import build_push_docs

    (tmp_path / "astloom.sync.yaml").write_text(
        "code:\n  exclude: []\ndocs:\n  match:\n    - '**/*.md'\n  exclude: []\n",
        encoding="utf-8",
    )
    for rel, doc_id in (
        ("backend/services/chat/README.md", "as.doc.chat.readme"),
        ("other/docs/README.md", "as.doc.other.readme"),
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            f"doc_id: {doc_id}\n"
            "title: Note\n"
            "doc_type: note\n"
            "status: active\n"
            "schema_version: '1.0'\n"
            "owner: tests\n"
            "summary: test\n"
            "tags: [test]\n"
            "phase: test\n"
            f"canonical_path: {rel}\n"
            "---\n\n# Note\n",
            encoding="utf-8",
        )
    args = Namespace(
        exclude_dir=[],
        include_path=["backend/services/chat"],
        include_ext=[],
        max_files=50,
    )
    docs = build_push_docs(tmp_path, args)
    ids = {d["doc_id"] for d in docs}
    assert "as.doc.chat.readme" in ids
    assert "as.doc.other.readme" not in ids


def test_fetch_remote_file_hashes_prefers_http(monkeypatch):
    import sys
    from types import ModuleType

    from astloom_cli.connect_config import ConnectSettings
    from astloom_cli.connect_flow import client_push as cp

    fake = ModuleType("httpx")

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"hashes": {"a.py": "abc"}}

    def get(url, headers=None, timeout=None, verify=None):
        assert "file-hashes" in url
        assert headers["Authorization"].startswith("Bearer ")
        return _Resp()

    fake.get = get  # type: ignore[attr-defined]
    fake.HTTPError = Exception  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", fake)

    settings = ConnectSettings(
        graph_url="http://g.internal:8080",
        api_token="tokentokentoken12",
        project="p",
        tenant="t",
        workspace="w",
    )
    assert cp._graph_http_ready(settings)
    hashes = cp.fetch_remote_file_hashes(settings, Namespace(project="p"))
    assert hashes == {"a.py": "abc"}


def test_cmd_ingest_push_applies_docs(monkeypatch):
    import io
    import sys

    from astloom_cli.commands import ingest_push as mod

    class _Svc:
        def ingest_pushed_sources(self, *_a, **_k):
            class _R:
                def to_dict(self):
                    return {"files_ingested": 0, "files_failed": 0}

            return _R()

        def upsert_human_documentation(self, *_a, **_k):
            return None

    monkeypatch.setattr(mod, "_graph_service", lambda: _Svc())
    monkeypatch.setattr(
        mod,
        "_graph_scope",
        lambda *_a, **_k: Namespace(project_id="p", tenant_id="t", workspace_id="w"),
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            '{"files":[],"docs":[{"doc_id":"as.doc.x","relative_path":"docs/x.md",'
            '"body":"# X","title":"X","linked_symbol_tokens":[]}]}'
        ),
    )
    printed: list[dict] = []
    monkeypatch.setattr(mod, "print_json", lambda obj: printed.append(obj))
    assert mod.cmd_ingest_push(Namespace(embedding_refresh_mode="touched")) == 0
    assert printed[0]["docs"]["docs_upserted"] == 1
