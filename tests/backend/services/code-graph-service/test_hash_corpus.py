"""GAP-T01 frozen hash corpus — format-only ≡, semantic/flag ≠, string literals safe."""

from __future__ import annotations

from pathlib import Path

import pytest

from code_graph_service.domain.hashing import (
    HASH_VERSION,
    _normalize_python_fallback,
    content_hash,
    extract_astloom_flags,
)

CORPUS = Path(__file__).resolve().parent / "hash_corpus" / "cases"

_LANG_CASES = (
    ("python", "python/format_a.py", "python/format_b.py"),
    ("javascript", "javascript/format_a.js", "javascript/format_b.js"),
    ("typescript", "typescript/format_a.ts", "typescript/format_b.ts"),
    ("go", "go/format_a.go", "go/format_b.go"),
    ("rust", "rust/format_a.rs", "rust/format_b.rs"),
    ("java", "java/format_a.java", "java/format_b.java"),
)

_SEMANTIC_CASES = (
    ("python", "python/semantic_a.py", "python/semantic_b.py"),
    ("javascript", "javascript/semantic_a.js", "javascript/semantic_b.js"),
    ("typescript", "typescript/semantic_a.ts", "typescript/semantic_b.ts"),
    ("go", "go/semantic_a.go", "go/semantic_b.go"),
    ("rust", "rust/semantic_a.rs", "rust/semantic_b.rs"),
    ("java", "java/semantic_a.java", "java/semantic_b.java"),
)

_FLAG_CASES = (
    ("python", "python/flag_a.py", "python/flag_b.py"),
    ("javascript", "javascript/flag_a.js", "javascript/flag_b.js"),
    ("typescript", "typescript/flag_a.ts", "typescript/flag_b.ts"),
    ("go", "go/flag_a.go", "go/flag_b.go"),
    ("rust", "rust/flag_a.rs", "rust/flag_b.rs"),
    ("java", "java/flag_a.java", "java/flag_b.java"),
)


def _read(rel: str) -> str:
    return (CORPUS / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize(("lang", "a", "b"), _LANG_CASES)
def test_format_only_same_hash(lang: str, a: str, b: str) -> None:
    ha = content_hash(_read(a), lang)
    hb = content_hash(_read(b), lang)
    assert ha["hash"] == hb["hash"]
    assert ha["hash_version"] == hb["hash_version"] == HASH_VERSION


@pytest.mark.parametrize(("lang", "a", "b"), _SEMANTIC_CASES)
def test_semantic_change_different_hash(lang: str, a: str, b: str) -> None:
    assert content_hash(_read(a), lang)["hash"] != content_hash(_read(b), lang)["hash"]


@pytest.mark.parametrize(("lang", "a", "b"), _FLAG_CASES)
def test_astloom_flag_change_different_hash(lang: str, a: str, b: str) -> None:
    assert content_hash(_read(a), lang)["hash"] != content_hash(_read(b), lang)["hash"]


def test_python_string_with_hash_not_stripped() -> None:
    src = _read("python/string_hash.py")
    assert "contains # hash" in src
    with_extra_ws = src + "\n\n"
    assert content_hash(src, "python")["hash"] == content_hash(with_extra_ws, "python")["hash"]
    mutated = src.replace("contains # hash", "contains # changed")
    assert content_hash(src, "python")["hash"] != content_hash(mutated, "python")["hash"]


def test_javascript_string_with_slashes_safe() -> None:
    src = _read("javascript/string_hash.js")
    assert content_hash(src, "javascript")["hash"]
    assert content_hash(src, "javascript")["hash"] == content_hash(src + "\n", "javascript")["hash"]


def test_normalize_via_tree_sitter_calls_parse_source_with_language_first(monkeypatch) -> None:
    """Regression: parse_source(language, file_path, source) — wrong order skipped AST path."""
    from code_graph_service.domain import hashing as hashing_mod

    calls: list[tuple] = []

    class _Parsed:
        canonical_text = "CANONICAL"

    def _fake_parse(language: str, file_path: str, source: str):
        calls.append((language, file_path, source))
        return _Parsed()

    monkeypatch.setattr(
        "code_graph_service.domain.parsers.parse_source",
        _fake_parse,
    )
    out = hashing_mod._normalize_via_tree_sitter("const x = 1;\n", "javascript")
    assert out == "CANONICAL"
    assert calls and calls[0][0] == "javascript"
    assert calls[0][2] == "const x = 1;\n"


def test_python_fallback_preserves_hash_in_strings() -> None:
    src = 'x = "# not comment"\ny = 1  # ordinary\n'
    normalized = _normalize_python_fallback(src)
    assert '# not comment' in normalized
    assert "ordinary" not in normalized


def test_python_flags_ignore_string_literals() -> None:
    src = 'msg = "astloom: fake"\n# astloom: real=1\n'
    flags = extract_astloom_flags(src, "python")
    assert flags == ["# astloom:real=1"]
