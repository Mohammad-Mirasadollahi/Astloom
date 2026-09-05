"""Tests for operator-owned sync filter config (required file + wildcards)."""

from __future__ import annotations

from pathlib import Path

import pytest

from astloom_cli.sync_config import (
    DEFAULT_INCLUDE_EXTENSIONS,
    SyncConfigError,
    resolve_sync_filters,
)
from code_graph_service.domain.repo_discovery import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_GLOBS,
    discover_source_files,
    path_matches_glob,
)


def test_missing_config_is_required(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_SYNC_EXCLUDE_DIRS", raising=False)
    with pytest.raises(SyncConfigError) as exc:
        resolve_sync_filters(root=tmp_path)
    msg = str(exc.value)
    assert "required sync filter file is missing" in msg
    assert "Create" in msg or "create" in msg
    assert "astloom.sync.yaml" in msg
    assert "exclude:" in msg or "code:" in msg


def test_missing_config_points_at_copyable_example(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_SYNC_EXCLUDE_DIRS", raising=False)
    (tmp_path / "astloom.sync.yaml.example").write_text("exclude: []\n", encoding="utf-8")
    with pytest.raises(SyncConfigError) as exc:
        resolve_sync_filters(root=tmp_path)
    msg = str(exc.value)
    assert "required sync filter file is missing" in msg
    assert "cp " in msg
    assert "astloom.sync.yaml.example" in msg
    assert str(tmp_path / "astloom.sync.yaml") in msg


def test_resolve_reads_repo_yaml_and_merges_cli(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_SYNC_EXCLUDE_DIRS", raising=False)
    monkeypatch.delenv("ASTLOOM_SYNC_INCLUDE_PATHS", raising=False)
    (tmp_path / "astloom.sync.yaml").write_text(
        "exclude:\n  - docs\n  - tests\n  - '**/generated/**'\ninclude_paths:\n  - backend/services\n",
        encoding="utf-8",
    )
    filters = resolve_sync_filters(
        root=tmp_path,
        cli_exclude_dirs=["fixtures", "**/*.min.js"],
        cli_include_paths=["backend/packages"],
    )
    assert "docs" in filters["exclude_dirs"]
    assert "tests" in filters["exclude_dirs"]
    assert "fixtures" in filters["exclude_dirs"]
    assert ".venv" not in filters["exclude_dirs"]  # no hardcoded builtins
    assert "**/generated/**" in filters["exclude_globs"]
    assert "**/*.min.js" in filters["exclude_globs"]
    assert filters["include_paths"] == ["backend/services", "backend/packages"]
    assert any(str(tmp_path / "astloom.sync.yaml") == s for s in filters["sources"])


def test_resolve_merges_gitignore_and_astloomignore(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_SYNC_EXCLUDE_DIRS", raising=False)
    (tmp_path / "astloom.sync.yaml").write_text("code:\n  exclude: [docs]\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("build/\n*.log\n", encoding="utf-8")
    (tmp_path / ".astloomignore").write_text("vendor/**\n", encoding="utf-8")
    filters = resolve_sync_filters(root=tmp_path)
    assert "docs" in filters["exclude_dirs"]
    assert any("build" in g or g.endswith("/**") for g in filters["exclude_globs"])
    assert "vendor/**" in filters["exclude_globs"] or any("vendor" in g for g in filters["exclude_globs"])
    assert filters["layered_ignore_globs"]
    assert len(filters["layered_ignore_sources"]) == 2
    monkeypatch.delenv("ASTLOOM_SYNC_EXCLUDE_DIRS", raising=False)
    (tmp_path / "astloom.sync.yaml").write_text(
        "exclude: [docs]\n",
        encoding="utf-8",
    )
    local = tmp_path / ".astloom"
    local.mkdir()
    (local / "sync.yaml").write_text(
        "exclude:\n  - only-this\n",
        encoding="utf-8",
    )
    filters = resolve_sync_filters(root=tmp_path)
    assert filters["exclude_dirs"] == ["only-this"]


def test_no_hardcoded_product_excludes():
    assert DEFAULT_EXCLUDE_DIRS == frozenset()
    assert DEFAULT_EXCLUDE_GLOBS == ()


def test_yaml_excludes_init_and_pycache(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_SYNC_EXCLUDE_DIRS", raising=False)
    (tmp_path / "astloom.sync.yaml").write_text(
        "\n".join(
            [
                "code:",
                "  exclude:",
                "    - '__pycache__'",
                "    - '**/__pycache__/**'",
                "    - '**/__init__.py'",
                "    - '**/*.pyc'",
                "    - '**/node_modules/**'",
                "",
            ]
        ),
        encoding="utf-8",
    )
    filters = resolve_sync_filters(root=tmp_path)
    assert "__pycache__" in filters["exclude_dirs"]
    assert "**/__pycache__/**" in filters["exclude_globs"]
    assert "**/__init__.py" in filters["exclude_globs"]
    assert "**/*.pyc" in filters["exclude_globs"]
    assert "**/node_modules/**" in filters["exclude_globs"]


def test_discover_skips_init_and_pycache_when_configured(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("# init\n", encoding="utf-8")
    (tmp_path / "pkg" / "mod.py").write_text("x=1\n", encoding="utf-8")
    cache = tmp_path / "pkg" / "__pycache__"
    cache.mkdir()
    (cache / "mod.cpython-312.pyc").write_bytes(b"\0")
    found = discover_source_files(
        tmp_path,
        include_extensions=[".py"],
        exclude_dirs=["__pycache__"],
        exclude_globs=["**/__init__.py", "**/__pycache__/**"],
    )
    rels = {f.relative_path for f in found}
    assert "pkg/mod.py" in rels
    assert "pkg/__init__.py" not in rels
    assert not any("__pycache__" in r for r in rels)


def test_path_matches_glob_patterns():
    assert path_matches_glob("backend/tests/a.py", "**/tests/**")
    assert path_matches_glob("tests/a.py", "**/tests/**")
    assert path_matches_glob("src/app.min.js", "**/*.min.js")
    assert path_matches_glob("pkg/foo_pb2.py", "**/*_pb2.py")
    assert not path_matches_glob("backend/services/a.py", "**/tests/**")
    # Interior **/ may span zero directories (gitignore-style).
    assert path_matches_glob("docs/a.md", "docs/**/*.md")
    assert path_matches_glob("docs/sub/a.md", "docs/**/*.md")
    assert path_matches_glob("backend/docs/x.md", "backend/docs/**/*.md")


def test_discover_respects_include_prefixes(tmp_path: Path):
    (tmp_path / "backend" / "services").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "backend" / "services" / "a.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "tests" / "t.py").write_text("x=1\n", encoding="utf-8")
    found = discover_source_files(
        tmp_path,
        include_extensions=[".py"],
        exclude_dirs=[".git"],
        exclude_globs=[],
        include_path_prefixes=["backend/services"],
    )
    rels = {f.relative_path for f in found}
    assert "backend/services/a.py" in rels
    assert "tests/t.py" not in rels


def test_discover_reinclude_globs(tmp_path: Path):
    (tmp_path / "keep.py").write_text("print('x')\n", encoding="utf-8")
    (tmp_path / "drop.py").write_text("print('y')\n", encoding="utf-8")
    found = discover_source_files(
        tmp_path,
        include_extensions=[".py"],
        exclude_dirs=[],
        exclude_globs=["*.py"],
        reinclude_globs=["keep.py"],
    )
    paths = {f.relative_path for f in found}
    assert "keep.py" in paths
    assert "drop.py" not in paths


def test_discover_exclude_globs_and_include_glob(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "src" / "app.min.js").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "lib" / "nested").mkdir(parents=True)
    (tmp_path / "lib" / "nested" / "x.py").write_text("x=1\n", encoding="utf-8")
    found = discover_source_files(
        tmp_path,
        include_extensions=[".py", ".js"],
        exclude_dirs=[".git"],
        exclude_globs=["**/*.min.js"],
        include_path_prefixes=["**/src/**"],
    )
    rels = {f.relative_path for f in found}
    assert "src/ok.py" in rels
    assert "src/app.min.js" not in rels
    assert "lib/nested/x.py" not in rels


def test_discover_skips_cpu_bench_when_excluded(tmp_path: Path):
    pkg = tmp_path / "pkg" / "_cpu_bench"
    pkg.mkdir(parents=True)
    (pkg / "mod_00.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "pkg" / "real.py").write_text("x=1\n", encoding="utf-8")
    found = discover_source_files(
        tmp_path,
        include_extensions=[".py"],
        exclude_dirs=["_cpu_bench"],
        exclude_globs=["**/_cpu_bench/**"],
    )
    rels = {f.relative_path for f in found}
    assert "pkg/real.py" in rels
    assert not any("_cpu_bench" in r for r in rels)


def test_tracked_sync_example_excludes_cpu_bench():
    example = Path(__file__).resolve().parents[4] / "astloom.sync.yaml.example"
    text = example.read_text(encoding="utf-8")
    assert "_cpu_bench" in text
    assert "**/_cpu_bench/**" in text


def test_default_and_example_include_mjs():
    assert ".mjs" in DEFAULT_INCLUDE_EXTENSIONS
    example = Path(__file__).resolve().parents[4] / "astloom.sync.yaml.example"
    text = example.read_text(encoding="utf-8")
    assert "- .mjs" in text


def test_resolve_defaults_include_mjs_when_yaml_omits_extensions(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_SYNC_INCLUDE_EXTENSIONS", raising=False)
    (tmp_path / "astloom.sync.yaml").write_text("code:\n  exclude: [tests]\n", encoding="utf-8")
    filters = resolve_sync_filters(root=tmp_path)
    assert ".mjs" in filters["include_extensions"]
