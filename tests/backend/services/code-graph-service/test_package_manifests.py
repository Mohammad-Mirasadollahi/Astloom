"""Phase F3: package-manager alias loading and import rewrite."""

from __future__ import annotations

from pathlib import Path

from code_graph_service.domain.cross_language import SymbolIndexes, resolve_import_target
from code_graph_service.domain.enums import CallConfidence, DocStatus, SymbolKind
from code_graph_service.domain.models import GraphSymbol, Scope
from code_graph_service.domain.package_manifests import load_package_aliases, rewrite_import


def test_load_aliases_from_pyproject_go_and_package_json(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "acme-tools"\n', encoding="utf-8")
    (tmp_path / "go.mod").write_text("module example.com/acme\n\ngo 1.22\n", encoding="utf-8")
    (tmp_path / "package.json").write_text(
        '{"name":"@acme/app","imports":{"#lib/*":"./src/lib/*"}}',
        encoding="utf-8",
    )
    aliases = load_package_aliases(tmp_path)
    assert aliases["acme-tools"] == "acme_tools"
    assert aliases["example.com/acme"] == "example.com/acme"
    assert "#lib" in aliases
    assert rewrite_import("acme-tools.core", aliases).startswith("acme_tools")


def test_load_aliases_from_cargo_tsconfig_and_go_replace(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "acme-core"\nversion = "0.1.0"\n\n'
        '[dependencies]\nhelper = { path = "crates/helper" }\n',
        encoding="utf-8",
    )
    (tmp_path / "go.mod").write_text(
        "module example.com/acme\n\n"
        "replace example.com/old => ./internal/old\n",
        encoding="utf-8",
    )
    (tmp_path / "tsconfig.json").write_text(
        '{"compilerOptions":{"paths":{"@app/*":["src/app/*"]}}}',
        encoding="utf-8",
    )
    aliases = load_package_aliases(tmp_path)
    assert aliases["acme-core"] == "acme_core"
    assert aliases["helper"] == "helper"
    assert aliases["example.com/old"] == "old"
    assert aliases["@app"] == "src/app"
    assert rewrite_import("@app/utils", aliases).startswith("src/app")


def test_resolve_import_uses_package_alias():
    scope = Scope("t", "w", "p")
    file_sym = GraphSymbol(
        id="file:p:src/lib/util.py",
        scope=scope,
        kind=SymbolKind.FILE,
        file_path="src/lib/util.py",
        name="util.py",
        qualified_name="src/lib/util.py",
        signature="",
        body="",
        hash_value="x",
        ai_documentation="",
        doc_status=DocStatus.UNCHANGED,
        embedding=[],
    )
    indexes = SymbolIndexes()
    indexes.symbols_by_id[file_sym.id] = file_sym
    indexes.by_file_stem["util"] = [file_sym.id]
    indexes.symbol_language[file_sym.id] = "python"

    target, conf, meta = resolve_import_target(
        "#lib/util",
        indexes,
        source_language="javascript",
        package_aliases={"#lib": "util"},
    )
    assert target == file_sym.id
    assert conf in {CallConfidence.PROBABLE, CallConfidence.EXACT}
    assert meta.get("import_rewritten_from") == "#lib/util" or meta.get("resolved_via")
