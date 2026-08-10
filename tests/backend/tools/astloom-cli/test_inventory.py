"""Tests for astloom inventory."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

from astloom_cli.commands.inventory import (
    TOP_N,
    _bucket,
    _pct,
    _rel_under,
    _top,
    format_detail_text,
    parse_inventory_words,
    cmd_inventory,
)
from astloom_cli.parser import build_parser


def test_inventory_summary_hints_sync_heal_when_embeddings_missing(capsys):
    from astloom_cli.commands.inventory.render import print_human

    print_human(
        {
            "scope": {"tenant": "t", "workspace": "w", "project": "p"},
            "paths": ["/tmp/app"],
            "summary": {
                "code": {
                    "done_count": 0,
                    "edited_count": 0,
                    "remaining_count": 0,
                    "total": 0,
                    "percent_done": 0.0,
                },
                "docs": {
                    "done_count": 0,
                    "edited_count": 0,
                    "remaining_count": 0,
                    "total": 0,
                    "percent_done": 0.0,
                },
                "llm": {"done_count": 0, "total": 0, "percent_done": 0.0},
                "embeddings": {
                    "indexed_symbols": 1,
                    "eligible_symbols": 5,
                    "coverage_percent": 20.0,
                    "missing_symbols": 4,
                },
            },
            "processing": {},
            "results": [],
            "models_used": [],
        },
        detail=False,
    )
    out = capsys.readouterr().out
    assert "Need embedding heal" in out
    assert "astloom sync heal" in out
    assert "missing=4" in out


def test_pending_work_line_is_count_only():
    from astloom_cli.commands.inventory.render import _edited_percent_line

    assert _edited_percent_line({"edited_count": 0, "remaining_count": 0, "total": 534}) == "none"
    assert _edited_percent_line({"edited_count": 4, "remaining_count": 0, "total": 237}) == "4 edited"
    assert (
        _edited_percent_line({"edited_count": 2, "remaining_count": 5, "total": 100})
        == "2 edited, 5 not indexed yet"
    )


def test_demote_edited_llm_moves_stale_symbols():
    from astloom_cli.commands.inventory.graph_index import demote_edited_llm

    done, remaining = demote_edited_llm(
        ["a.py::f", "b.py::g"],
        ["c.py::h"],
        {"b.py"},
    )
    assert done == ["a.py::f"]
    assert remaining == ["c.py::h", "b.py::g"]


def test_collect_facade_reexports():
    from astloom_cli.commands.inventory import collect

    assert callable(collect.build_inventory_report)
    assert callable(collect.inventory_one_root)
    assert callable(collect.language_breakdown)


def test_parser_inventory_word_modes():
    parser = build_parser()
    args = parser.parse_args(["inventory"])
    assert args.command == "inventory"
    assert args.words == []

    detailed = parser.parse_args(["inventory", "detail"])
    assert detailed.words == ["detail"]

    saved = parser.parse_args(["inventory", "save", "/tmp/inv.txt"])
    assert saved.words == ["save", "/tmp/inv.txt"]

    both = parser.parse_args(["inventory", "detail", "save", "/tmp/inv.txt"])
    assert both.words == ["detail", "save", "/tmp/inv.txt"]


def test_parse_inventory_words():
    assert parse_inventory_words([]) == (False, "")
    assert parse_inventory_words(["detail"]) == (True, "")
    assert parse_inventory_words(["save", "/tmp/a.txt"]) == (False, "/tmp/a.txt")
    assert parse_inventory_words(["detail", "save", "/tmp/a.txt"]) == (True, "/tmp/a.txt")
    with pytest.raises(SystemExit):
        parse_inventory_words(["save"])
    with pytest.raises(SystemExit):
        parse_inventory_words(["--detail"])


def test_pct_and_bucket_and_top():
    assert _pct(0, 0) == 100.0
    assert _pct(1, 4) == 25.0
    bucket = _bucket(["a.py"], ["b.py", "c.py"])
    assert bucket["done_count"] == 1
    assert bucket["remaining_count"] == 2
    assert bucket["total"] == 3
    assert bucket["percent_done"] == 33.3
    rows = [{"file": f"f{i}.py"} for i in range(15)]
    assert len(_top(rows)) == TOP_N
    assert TOP_N == 10


def test_rel_under(tmp_path: Path):
    root = tmp_path / "app"
    root.mkdir()
    assert _rel_under(root, "src/main.py") == "src/main.py"
    assert _rel_under(root, str(root / "src" / "main.py")) == "src/main.py"
    assert _rel_under(root, "__astloom__/last_sync") is None


def test_format_detail_text_contains_file_models():
    report = {
        "scope": {"tenant": "t", "workspace": "w", "project": "p"},
        "paths": ["/opt/App"],
        "processing": {"docs_model_label": "heuristic", "active_embed_model": "stub:local"},
        "models_used": ["heuristic", "stub:local"],
        "summary": {
            "code": {
                "done_count": 1,
                "edited_count": 1,
                "remaining_count": 1,
                "total": 3,
                "percent_done": 33.3,
                "percent_edited": 33.3,
                "percent_remaining": 33.3,
            },
            "docs": {
                "done_count": 0,
                "edited_count": 0,
                "remaining_count": 1,
                "total": 1,
                "percent_done": 0.0,
                "percent_edited": 0.0,
                "percent_remaining": 100.0,
            },
            "llm": {"done_count": 0, "remaining_count": 1, "total": 1, "percent_done": 0.0},
        },
        "results": [
            {
                "path": "/opt/App",
                "code": {
                    "percent_done": 33.3,
                    "percent_edited": 33.3,
                    "percent_remaining": 33.3,
                    "done_files": [
                        {
                            "file": "a.py",
                            "status": "done",
                            "edit_reason": "",
                            "models": ["stub:local", "heuristic"],
                            "embed_models": ["stub:local"],
                            "docs_models": ["heuristic"],
                            "symbols": 2,
                            "documented": 1,
                            "doc_percent": 50.0,
                        }
                    ],
                    "edited_files": [
                        {
                            "file": "c.py",
                            "status": "edited",
                            "edit_reason": "content_changed",
                            "models": ["stub:local"],
                            "embed_models": ["stub:local"],
                            "docs_models": [],
                            "symbols": 1,
                            "documented": 0,
                            "doc_percent": 0.0,
                        }
                    ],
                    "remaining_files": [
                        {
                            "file": "b.py",
                            "status": "remaining",
                            "edit_reason": "",
                            "models": [],
                            "embed_models": [],
                            "docs_models": [],
                            "symbols": 0,
                            "documented": 0,
                            "doc_percent": 100.0,
                        }
                    ],
                    "top_done": [],
                    "top_edited": [],
                    "top_remaining": [],
                },
                "docs": {
                    "percent_done": 0.0,
                    "percent_edited": 0.0,
                    "percent_remaining": 100.0,
                    "done_files": [],
                    "edited_files": [],
                    "remaining_files": [
                        {
                            "file": "README.md",
                            "status": "remaining",
                            "edit_reason": "",
                            "models": [],
                            "embed_models": [],
                            "docs_models": [],
                            "symbols": 0,
                            "documented": 0,
                            "doc_percent": 100.0,
                        }
                    ],
                    "top_done": [],
                    "top_edited": [],
                    "top_remaining": [],
                },
            }
        ],
    }
    text = format_detail_text(report)
    assert "33.3%" in text
    assert "a.py" in text
    assert "c.py" in text
    assert "content_changed" in text
    assert "Code edited" in text
    assert "README.md" in text


def test_classify_edited_pending_and_hash(tmp_path: Path):
    from astloom_cli.commands.inventory.edited import classify_edited_paths, disk_content_hash
    from code_graph_service.domain.hashing import content_hash

    root = tmp_path / "app"
    (root / "src").mkdir(parents=True)
    path = root / "src" / "x.py"
    path.write_text("def x():\n    return 1\n", encoding="utf-8")
    good_hash = str(content_hash(path.read_text(encoding="utf-8"), "python")["hash"])
    assert disk_content_hash(path, "python") == good_hash

    edited = classify_edited_paths(
        root_path=root,
        indexed={"src/x.py", "src/y.py"},
        pending_rels={"src/y.py"},
        file_meta={
            "src/x.py": {"hash": "stale-hash", "language": "python"},
            "src/y.py": {"hash": good_hash, "language": "python"},
        },
    )
    assert edited["src/x.py"] == "content_changed"
    assert edited["src/y.py"] == "pending"


def test_inventory_one_root_classifies_with_models(tmp_path: Path, monkeypatch):
    from astloom_cli.commands import inventory as inv
    from code_graph_service.domain.hashing import content_hash, digest

    app = tmp_path / "app"
    (app / "src").mkdir(parents=True)
    (app / "docs").mkdir()
    done_src = "def ok():\n    return 1\n"
    edited_src = "def changed():\n    return 9\n"
    (app / "src" / "done.py").write_text(done_src, encoding="utf-8")
    (app / "src" / "edited.py").write_text(edited_src, encoding="utf-8")
    (app / "src" / "todo.py").write_text("def pending():\n    return 2\n", encoding="utf-8")
    (app / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    done_hash = str(content_hash(done_src, "python")["hash"])
    stale_hash = str(content_hash("def old():\n    return 0\n", "python")["hash"])

    symbols = [
        SimpleNamespace(
            id="file:done",
            kind=SimpleNamespace(value="file"),
            file_path="src/done.py",
            qualified_name="src/done.py",
            name="done.py",
            doc_status=SimpleNamespace(value="unchanged"),
            ai_documentation="",
            hash_value=done_hash,
            language="python",
        ),
        SimpleNamespace(
            id="file:edited",
            kind=SimpleNamespace(value="file"),
            file_path="src/edited.py",
            qualified_name="src/edited.py",
            name="edited.py",
            doc_status=SimpleNamespace(value="unchanged"),
            ai_documentation="",
            hash_value=stale_hash,
            language="python",
        ),
        SimpleNamespace(
            id="fn:ok",
            kind=SimpleNamespace(value="function"),
            file_path="src/done.py",
            qualified_name="done.ok",
            name="ok",
            doc_status=SimpleNamespace(value="generated"),
            ai_documentation="ok fn",
            hash_value="x",
            language="python",
        ),
        SimpleNamespace(
            id="fn:changed",
            kind=SimpleNamespace(value="function"),
            file_path="src/edited.py",
            qualified_name="edited.changed",
            name="changed",
            doc_status=SimpleNamespace(value="generated"),
            ai_documentation="stale docs",
            hash_value="y",
            language="python",
        ),
        SimpleNamespace(
            id="doc:guide",
            kind=SimpleNamespace(value="documentation"),
            file_path="docs/guide.md",
            qualified_name="human:guide",
            name="guide.md",
            doc_status=SimpleNamespace(value="human"),
            ai_documentation="Guide",
            hash_value=digest("# Guide\n"),
            language="",
        ),
    ]
    store = SimpleNamespace(list_symbols=lambda _scope: symbols)
    index = SimpleNamespace(
        list_symbol_models=lambda _scope: {
            "fn:ok": "local_bge:test-model",
            "fn:changed": "local_bge:test-model",
        }
    )
    svc = SimpleNamespace(
        store=store,
        freshness_status=lambda _scope: {"pending_files": []},
        embedding_index=index,
        embeddings=SimpleNamespace(model="local_bge:test-model"),
        llm_config=lambda: {
            "docs_enabled": False,
            "route_docs": {"primary_model": "", "fallback_models": []},
            "route_embed": {"primary_model": "", "fallback_models": []},
        },
    )
    scope = SimpleNamespace(tenant_id="t", workspace_id="w", project_id="p")

    monkeypatch.setattr(
        "astloom_cli.commands.inventory.root.resolve_sync_filters",
        lambda **_k: {
            "include_extensions": [".py"],
            "exclude_dirs": set(),
            "exclude_globs": [],
            "include_paths": [],
            "docs_enabled": True,
            "doc_match_globs": ["docs/*.md"],
            "doc_exclude_dirs": set(),
            "doc_exclude_globs": [],
            "doc_paths": [],
            "sources": ["test"],
        },
    )

    row = inv._inventory_one_root(svc=svc, scope=scope, root_path=app, max_files=2000)
    assert "src/done.py" in row["code"]["done"]
    assert "src/edited.py" in row["code"]["edited"]
    assert "src/todo.py" in row["code"]["remaining"]
    assert row["code"]["edited_files"][0]["edit_reason"] == "content_changed"
    assert "docs/guide.md" in row["docs"]["done"]
    assert row["code"]["llm"]["done_count"] == 1
    assert row["code"]["llm"]["remaining_count"] == 1
    assert row["code"]["llm"]["total"] == 2
    assert row["code"]["llm"]["percent_done"] == 50.0
    assert any(label.startswith("src/edited.py::") for label in row["code"]["llm"]["remaining"])
    assert len(row["code"]["top_edited"]) <= TOP_N
    top = row["code"]["top_done"][0]
    assert top["file"] == "src/done.py"
    assert "local_bge:test-model" in top["embed_models"]
    assert "heuristic" in top["docs_models"]
    assert "local_bge:test-model" in row["models_used"]
    assert row["code"]["embeddings"] == {
        "eligible_symbols": 2,
        "indexed_symbols": 2,
        "missing_symbols": 0,
        "coverage_percent": 100.0,
    }

    index.list_symbol_models = lambda _scope: {"fn:ok": "local_bge:test-model"}
    (app / "docs" / "guide.md").write_text("# Guide changed\n", encoding="utf-8")
    degraded = inv._inventory_one_root(
        svc=svc,
        scope=scope,
        root_path=app,
        max_files=2000,
    )
    assert degraded["code"]["embeddings"]["missing_symbols"] == 1
    assert degraded["code"]["edited_files"][0]["embed_models"] == []
    assert degraded["docs"]["edited"] == ["docs/guide.md"]
    assert degraded["docs"]["edited_files"][0]["edit_reason"] == "content_changed"


def test_cmd_inventory_save(tmp_path: Path, monkeypatch, capsys):
    report = {
        "scope": {"tenant": "t", "workspace": "w", "project": "p"},
        "paths": [str(tmp_path)],
        "processing": {"docs_model_label": "heuristic", "active_embed_model": "stub"},
        "models_used": ["heuristic"],
        "summary": {
            "code": {
                "done_count": 0,
                "edited_count": 0,
                "remaining_count": 1,
                "total": 1,
                "percent_done": 0.0,
                "percent_edited": 0.0,
                "percent_remaining": 100.0,
            },
            "docs": {
                "done_count": 0,
                "edited_count": 0,
                "remaining_count": 0,
                "total": 0,
                "percent_done": 100.0,
                "percent_edited": 0.0,
                "percent_remaining": 0.0,
            },
            "llm": {"done_count": 0, "remaining_count": 0, "total": 0, "percent_done": 100.0},
        },
        "results": [
            {
                "path": str(tmp_path),
                "code": {
                    "percent_done": 0.0,
                    "percent_edited": 0.0,
                    "percent_remaining": 100.0,
                    "done_files": [],
                    "edited_files": [],
                    "remaining_files": [
                        {
                            "file": "x.py",
                            "status": "remaining",
                            "edit_reason": "",
                            "models": [],
                            "embed_models": [],
                            "docs_models": [],
                            "symbols": 0,
                            "documented": 0,
                            "doc_percent": 100.0,
                        }
                    ],
                    "top_done": [],
                    "top_edited": [],
                    "top_remaining": [],
                },
                "docs": {
                    "percent_done": 100.0,
                    "percent_edited": 0.0,
                    "percent_remaining": 0.0,
                    "done_files": [],
                    "edited_files": [],
                    "remaining_files": [],
                    "top_done": [],
                    "top_edited": [],
                    "top_remaining": [],
                },
            }
        ],
    }
    monkeypatch.setattr(
        "astloom_cli.commands.inventory.cmd.build_inventory_report",
        lambda _args: report,
    )
    out = tmp_path / "details.txt"
    args = argparse.Namespace(words=["save", str(out)])
    assert cmd_inventory(args) == 0
    text = out.read_text(encoding="utf-8")
    assert "x.py" in text
    assert "0.0%" in text
    captured = capsys.readouterr().out
    assert "Inventory" in captured
    assert "Top 10" in captured
    assert "edited" in captured.lower()
    assert "Saved" in captured
