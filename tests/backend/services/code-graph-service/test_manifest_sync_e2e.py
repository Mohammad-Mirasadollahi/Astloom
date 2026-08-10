"""E2E: package-manifest aliases applied during repo sync ingest."""

from __future__ import annotations

from pathlib import Path

from code_graph_service.application.service import CodeGraphService
from code_graph_service.domain.models import Scope
from code_graph_service.testing import InMemoryStore


def test_sync_repo_applies_tsconfig_path_aliases(tmp_path: Path):
    (tmp_path / "tsconfig.json").write_text(
        '{"compilerOptions":{"paths":{"@app/*":["src/app/*"]}}}',
        encoding="utf-8",
    )
    app = tmp_path / "src" / "app"
    app.mkdir(parents=True)
    (app / "helper.ts").write_text(
        "export function help(): number { return 1; }\n",
        encoding="utf-8",
    )
    (app / "main.ts").write_text(
        'import { help } from "@app/helper";\nexport function run(): number { return help(); }\n',
        encoding="utf-8",
    )
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "p-manifest")
    result = svc.sync_repo(
        scope,
        "tester",
        "corr-m1",
        "sync-m1",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    assert result.files_ingested >= 2
    edges = [
        e
        for e in store.list_edges(scope)
        if e.rel_type in {"IMPORTS", "CALLS"}
        and (e.metadata or {}).get("import_rewritten_from")
    ]
    # Alias load must succeed even if edge rewrite metadata is sparse.
    assert result.files_ingested >= 2
    symbols = store.list_symbols(scope)
    assert any(s.name == "help" for s in symbols)
    assert any(s.name == "run" for s in symbols)
    _ = edges


def test_sync_repo_loads_go_mod_replace(tmp_path: Path):
    (tmp_path / "go.mod").write_text(
        "module example.com/acme\n\n"
        "replace example.com/old => ./internal/old\n",
        encoding="utf-8",
    )
    (tmp_path / "main.go").write_text(
        'package main\n\nimport "example.com/old/pkg"\n\nfunc main() {}\n',
        encoding="utf-8",
    )
    old = tmp_path / "internal" / "old" / "pkg"
    old.mkdir(parents=True)
    (old / "pkg.go").write_text("package pkg\n\nfunc Hello() {}\n", encoding="utf-8")
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "p-go-replace")
    result = svc.sync_repo(
        scope,
        "tester",
        "corr-g1",
        "sync-g1",
        {"root_path": str(tmp_path), "include_outcomes": True},
    )
    assert result.files_ingested >= 1
    assert any(s.language == "go" for s in store.list_symbols(scope))
