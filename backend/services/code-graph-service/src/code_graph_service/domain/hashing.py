"""
Role: language-aware content hashing for code-graph ingest (GAP-T01).
SoT / invariants: HASH_VERSION bumps invalidate prior digests; astloom doc-flags must affect hash.
Allowed failures: SyntaxError/parse failure falls back to normalized source digest.
Forbidden failures: stripping string-literal comment markers; ignoring astloom: flags.
"""

from __future__ import annotations

import ast
import io
import sys
import tokenize
from datetime import UTC, datetime
from hashlib import sha256
import importlib.metadata
import re
from typing import Any


HASH_VERSION = "4"
_ASTLOOM_FLAG = re.compile(r"astloom\s*:", re.IGNORECASE)
_ASTLOOM_BODY = re.compile(r"astloom\s*:\s*(.*)$", re.IGNORECASE)


def digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def parser_version(language: str = "python") -> str:
    lang = (language or "python").strip().lower() or "python"
    if lang == "python":
        major, minor = sys.version_info[:2]
        return f"stdlib_ast:{major}.{minor}"
    try:
        ver = importlib.metadata.version("tree-sitter")
    except importlib.metadata.PackageNotFoundError:
        ver = "unknown"
    return f"tree_sitter:{lang}:{ver}"


def _canonical_flag(raw: str) -> str:
    match = _ASTLOOM_BODY.search(raw.strip())
    if not match:
        return raw.strip()
    return f"# astloom:{match.group(1).strip()}"


def extract_astloom_flags(source: str, language: str = "python") -> list[str]:
    """Collect Astloom doc-flag comments (string-literal safe for Python)."""
    lang = (language or "python").strip().lower() or "python"
    if lang == "python":
        return _extract_python_flags(source)
    flags: list[str] = []
    for line in source.splitlines():
        if _ASTLOOM_FLAG.search(line):
            flags.append(_canonical_flag(line))
    return flags


def _extract_python_flags(source: str) -> list[str]:
    flags: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT and _ASTLOOM_FLAG.search(tok.string):
                flags.append(_canonical_flag(tok.string))
    except (tokenize.TokenError, IndentationError):
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") and _ASTLOOM_FLAG.search(stripped):
                flags.append(_canonical_flag(stripped))
    return flags


def normalize_source(source: str, language: str = "python") -> str:
    """Canonical text used when AST/tree canonicalization is unavailable."""
    normalized_language = (language or "python").strip().lower() or "python"
    flags = extract_astloom_flags(source, normalized_language)
    if normalized_language == "python":
        body = _normalize_python_fallback(source)
    elif normalized_language in {"javascript", "typescript", "go", "rust", "java"}:
        body = _normalize_via_tree_sitter(source, normalized_language)
    else:
        body = _normalize_python_fallback(source)
    if flags:
        return body + "\n" + "\n".join(flags)
    return body


def content_hash(source: str, language: str = "python") -> dict[str, Any]:
    lang = (language or "python").strip().lower() or "python"
    if lang == "python":
        material = _python_ast_material(source)
    else:
        material = normalize_source(source, lang)
    return {
        "hash": digest(material),
        "hash_version": HASH_VERSION,
        "parser_version": parser_version(lang),
    }


def _python_ast_material(source: str) -> str:
    flags = extract_astloom_flags(source, "python")
    try:
        tree = ast.parse(source)
        dumped = ast.dump(tree, annotate_fields=True, include_attributes=False)
    except SyntaxError:
        dumped = _normalize_python_fallback(source)
    if flags:
        return dumped + "\n" + "\n".join(flags)
    return dumped


def _normalize_python_fallback(source: str) -> str:
    """Tokenize-based normalize — never split on '#' inside string literals."""
    parts: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                continue
            if tok.type in (tokenize.NL, tokenize.NEWLINE):
                parts.append("\n")
                continue
            if tok.type in (
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.ENCODING,
                tokenize.ENDMARKER,
            ):
                continue
            parts.append(tok.string)
    except (tokenize.TokenError, IndentationError):
        return "\n".join(ln.rstrip() for ln in source.splitlines() if ln.strip())
    text = "".join(parts)
    lines = [re.sub(r"\s+", " ", ln.strip()) for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def _normalize_via_tree_sitter(source: str, language: str) -> str:
    try:
        from code_graph_service.domain.parsers import parse_source
    except Exception:
        return _normalize_c_family_fallback(source)
    ext = {
        "javascript": ".js",
        "typescript": ".ts",
        "go": ".go",
        "rust": ".rs",
        "java": ".java",
    }.get(language, ".txt")
    try:
        # parse_source(language, file_path, source) — order matters (GAP-T01).
        parsed = parse_source(language, f"<hash-normalize>{ext}", source)
        if hasattr(parsed, "canonical_text"):
            return str(parsed.canonical_text)
        if hasattr(parsed, "root") and hasattr(parsed.root, "sexp"):
            return str(parsed.root.sexp())
    except Exception:
        pass
    return _normalize_c_family_fallback(source)


def _normalize_c_family_fallback(source: str) -> str:
    """Strip comments outside strings using a small state machine."""
    out: list[str] = []
    i = 0
    n = len(source)
    in_str: str | None = None
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(source[i + 1])
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in {'"', "'", "`"}:
            in_str = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            line_end = source.find("\n", i)
            comment = source[i:] if line_end < 0 else source[i:line_end]
            if _ASTLOOM_FLAG.search(comment):
                out.append(_canonical_flag(comment))
            i = n if line_end < 0 else line_end
            continue
        if ch == "/" and nxt == "*":
            end = source.find("*/", i + 2)
            block = source[i:] if end < 0 else source[i : end + 2]
            if _ASTLOOM_FLAG.search(block):
                out.append(_canonical_flag(block))
            i = n if end < 0 else end + 2
            continue
        out.append(ch)
        i += 1
    text = "".join(out)
    lines = [re.sub(r"\s+", " ", ln.strip()) for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
