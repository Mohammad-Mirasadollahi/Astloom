"""Load operator-owned sync filters (required YAML + wildcards)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from astloom_cli.util import ensure_service_import_paths

ensure_service_import_paths()

from code_graph_service.domain.doc_discovery import DEFAULT_DOC_MATCH_GLOBS
from code_graph_service.domain.repo_discovery import _looks_like_glob, default_include_extensions

from astloom_cli.docs_audit_scope import merge_docs_audit_exclude_globs

# Same set as LANGUAGE_MATRIX (includes .mjs / .cjs / .mts / .cts / .java).
DEFAULT_INCLUDE_EXTENSIONS = default_include_extensions()

REPO_CONFIG_NAMES = ("astloom.sync.yaml", "astloom.sync.yml")
LOCAL_CONFIG_REL = Path(".astloom") / "sync.yaml"


class SyncConfigError(SystemExit):
    """Raised when the required sync filter file is missing or invalid."""


def _as_str_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [p.strip() for p in raw.split(",") if p.strip()]
    if isinstance(raw, (list, tuple)):
        out: list[str] = []
        for item in raw:
            text = str(item or "").strip()
            if text:
                out.append(text)
        return out
    return []


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise SyncConfigError(f"error: invalid sync config YAML at {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise SyncConfigError(f"error: sync config must be a YAML mapping: {path}")
    return doc


def _normalize_ext(ext: str) -> str:
    text = ext.strip().lower()
    if not text:
        return ""
    return text if text.startswith(".") else f".{text}"


def _normalize_pattern(prefix: str) -> str:
    return prefix.strip().replace("\\", "/").lstrip("./")


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _split_dir_and_glob(patterns: list[str]) -> tuple[set[str], list[str]]:
    dirs: set[str] = set()
    globs: list[str] = []
    for raw in patterns:
        text = _normalize_pattern(raw)
        if not text:
            continue
        if _looks_like_glob(text) or "/" in text:
            globs.append(text)
        else:
            dirs.add(text.lower())
    return dirs, globs


def _section(merged: dict[str, Any], name: str) -> dict[str, Any]:
    raw = merged.get(name)
    return raw if isinstance(raw, dict) else {}


def find_sync_config_paths(root: Path) -> list[Path]:
    """Return existing config files in merge order (repo then local)."""
    root = root.expanduser().resolve()
    found: list[Path] = []
    for name in REPO_CONFIG_NAMES:
        path = root / name
        if path.is_file():
            found.append(path)
            break
    local = root / LOCAL_CONFIG_REL
    if local.is_file():
        found.append(local)
    return found


def require_sync_config(root: Path) -> list[Path]:
    """Require at least one sync filter file under ``root``."""
    found = find_sync_config_paths(root)
    if found:
        return found

    root = root.expanduser().resolve()
    example = root / "astloom.sync.yaml.example"
    target = root / "astloom.sync.yaml"

    lines = [
        "error: required sync filter file is missing — create it before running sync.",
        f"  Sync root: {root}",
        "  Expected one of:",
        "    - astloom.sync.yaml          (recommended; local — gitignored)",
        "    - astloom.sync.yml",
        "    - .astloom/sync.yaml         (local-only override)",
        "",
        "  How to create it:",
    ]
    if example.is_file():
        lines.extend(
            [
                "    Copy the template, then edit code.exclude / docs.match:",
                f"      cp {example} {target}",
                "    Or from the sync root:",
                "      cp astloom.sync.yaml.example astloom.sync.yaml",
            ]
        )
    else:
        lines.extend(
            [
                "    No astloom.sync.yaml.example found in this sync root.",
                "    Create astloom.sync.yaml with at least:",
                "",
                "      code:",
                "        exclude:",
                "          - tests",
                "      docs:",
                "        match:",
                "          - '**/*.md'",
                "          - '**/*.mdx'",
                "        exclude: []",
                "",
            ]
        )
    lines.extend(
        [
            "",
            "  Patterns support wildcards: *, ?, [], **  (e.g. '**/tests/**', '**/*.md')",
            "  Docs: docs/08-software-engineering-architecture/42-astloom-cli-command-reference.md#sync-filters",
        ]
    )
    raise SyncConfigError("\n".join(lines))


def _merge_exclude(
    *,
    user_patterns: list[str],
    env_value: str,
    cli_patterns: list[str],
) -> tuple[list[str], list[str]]:
    """Build exclude dirs/globs from config/env/CLI only (no hardcoded product list)."""
    user_dirs, user_globs = _split_dir_and_glob(user_patterns)
    exclude_dirs: set[str] = set(user_dirs)
    exclude_globs: list[str] = list(user_globs)
    if env_value.strip():
        d, g = _split_dir_and_glob(_as_str_list(env_value))
        exclude_dirs |= d
        exclude_globs.extend(g)
    d, g = _split_dir_and_glob(list(cli_patterns or []))
    exclude_dirs |= d
    exclude_globs.extend(g)
    return sorted(exclude_dirs), _dedupe(exclude_globs)


def resolve_sync_filters(
    *,
    root: Path,
    cli_exclude_dirs: list[str] | None = None,
    cli_include_paths: list[str] | None = None,
    cli_include_extensions: list[str] | None = None,
    require_config: bool = True,
) -> dict[str, Any]:
    """Merge required config ← env ← CLI.

    Preferred schema (separate code vs docs excludes — edit astloom.sync.yaml):

    ```yaml
    code:
      exclude: [...]
      include_extensions: [.py, ...]
    docs:
      match: ['**/*.md', '**/*.mdx']
      exclude: [...]          # Phase 2 discovery skip
      audit:
        exclude: [...]         # Full-tier / quality-audit skip (still may sync)
    ```

    Code/path discovery excludes are operator-owned YAML (no hardcoded product
    tree list). Docs audit always merges built-in README/AGENTS defaults with
    ``docs.audit.exclude``. Legacy top-level ``exclude`` / ``doc_paths`` /
    ``include_paths`` still work.
    """
    root = root.expanduser().resolve()
    sources = [str(p) for p in (require_sync_config(root) if require_config else find_sync_config_paths(root))]
    if require_config and not sources:
        require_sync_config(root)

    merged: dict[str, Any] = {}
    for path_s in sources:
        data = _load_yaml(Path(path_s))
        merged.update(data)

    code_sec = _section(merged, "code")
    docs_sec = _section(merged, "docs")

    # --- code excludes (Phase 1) ---
    code_patterns = (
        _as_str_list(code_sec.get("exclude"))
        + _as_str_list(merged.get("exclude"))
        + _as_str_list(merged.get("exclude_dirs"))
        + _as_str_list(merged.get("exclude_globs"))
        + _as_str_list(code_sec.get("exclude_dirs"))
        + _as_str_list(code_sec.get("exclude_globs"))
    )
    # CI-45 / RM-05: layered ignore files under the software root.
    layered_globs: list[str] = []
    layered_sources: list[str] = []
    layered_reinclude: list[str] = []
    try:
        from repo_pack import collect_layered_ignore_globs, collect_layered_reinclude_globs

        layered_globs, layered_sources = collect_layered_ignore_globs(root)
        layered_reinclude = collect_layered_reinclude_globs(root)
        code_patterns = code_patterns + list(layered_globs)
    except ImportError:
        layered_globs, layered_sources, layered_reinclude = [], [], []

    exclude_dirs, exclude_globs = _merge_exclude(
        user_patterns=code_patterns,
        env_value=os.environ.get("ASTLOOM_SYNC_EXCLUDE_DIRS", ""),
        cli_patterns=list(cli_exclude_dirs or []),
    )

    # --- code language extensions (not path includes) ---
    if cli_include_extensions:
        exts_raw = list(cli_include_extensions)
    else:
        env_ext = os.environ.get("ASTLOOM_SYNC_INCLUDE_EXTENSIONS", "").strip()
        if env_ext:
            exts_raw = _as_str_list(env_ext)
        else:
            exts_raw = (
                _as_str_list(code_sec.get("include_extensions"))
                or _as_str_list(merged.get("include_extensions"))
                or list(DEFAULT_INCLUDE_EXTENSIONS)
            )
    extensions = [_normalize_ext(e) for e in exts_raw if _normalize_ext(e)]

    # Path allow-list is optional/legacy only (prefer exclude-only).
    include_paths = [_normalize_pattern(p) for p in _as_str_list(merged.get("include_paths"))]
    include_paths.extend(_normalize_pattern(p) for p in _as_str_list(merged.get("include")))
    include_paths.extend(_normalize_pattern(p) for p in _as_str_list(code_sec.get("include_paths")))
    env_inc = os.environ.get("ASTLOOM_SYNC_INCLUDE_PATHS", "").strip()
    if env_inc:
        include_paths.extend(_normalize_pattern(p) for p in _as_str_list(env_inc))
    include_paths.extend(_normalize_pattern(p) for p in (cli_include_paths or []) if str(p).strip())
    include_paths = _dedupe([p for p in include_paths if p])

    # --- docs match + docs excludes (Phase 2) ---
    docs_enabled = True
    if "enabled" in docs_sec:
        docs_enabled = bool(docs_sec.get("enabled"))

    # Explicit empty match disables Phase 2.
    explicit_empty_match = (
        ("match" in docs_sec and docs_sec.get("match") == [])
        or ("include_globs" in docs_sec and docs_sec.get("include_globs") == [])
    )

    match_globs = _as_str_list(docs_sec.get("match")) + _as_str_list(docs_sec.get("include_globs"))
    env_match = os.environ.get("ASTLOOM_SYNC_DOC_MATCH", "").strip()
    if env_match:
        match_globs.extend(_as_str_list(env_match))

    # Legacy doc_paths → prefix-narrowed match, or disable when explicit empty.
    legacy_paths = [_normalize_pattern(p) for p in _as_str_list(merged.get("doc_paths"))]
    env_docs = os.environ.get("ASTLOOM_SYNC_DOC_PATHS", "").strip()
    if env_docs:
        legacy_paths.extend(_normalize_pattern(p) for p in _as_str_list(env_docs))
    legacy_paths = _dedupe([p for p in legacy_paths if p])

    if explicit_empty_match or ("doc_paths" in merged and not legacy_paths and not env_docs and not match_globs and not env_match):
        match_globs = []
        docs_enabled = False
        legacy_paths = []
    elif not match_globs and docs_enabled:
        if legacy_paths:
            synthesized: list[str] = []
            for prefix in legacy_paths:
                synthesized.extend([f"{prefix}/**/*.md", f"{prefix}/**/*.mdx"])
            match_globs = synthesized
        else:
            match_globs = list(DEFAULT_DOC_MATCH_GLOBS)

    match_globs = _dedupe([_normalize_pattern(p) for p in match_globs if p])
    if not match_globs:
        docs_enabled = False
        legacy_paths = []

    docs_patterns = (
        _as_str_list(docs_sec.get("exclude"))
        + _as_str_list(docs_sec.get("exclude_dirs"))
        + _as_str_list(docs_sec.get("exclude_globs"))
    )
    doc_exclude_dirs, doc_exclude_globs = _merge_exclude(
        user_patterns=docs_patterns,
        env_value=os.environ.get("ASTLOOM_SYNC_DOC_EXCLUDE", ""),
        cli_patterns=[],
    )

    audit_sec = docs_sec.get("audit")
    audit_sec = audit_sec if isinstance(audit_sec, dict) else {}
    audit_patterns = (
        _as_str_list(audit_sec.get("exclude"))
        + _as_str_list(audit_sec.get("exclude_globs"))
        + _as_str_list(os.environ.get("ASTLOOM_SYNC_DOC_AUDIT_EXCLUDE", ""))
    )
    doc_audit_exclude_globs = merge_docs_audit_exclude_globs(audit_patterns)

    return {
        "exclude_dirs": exclude_dirs,
        "exclude_globs": exclude_globs,
        "include_paths": include_paths,
        "include_extensions": extensions,
        "doc_match_globs": match_globs if docs_enabled else [],
        "doc_exclude_dirs": doc_exclude_dirs,
        "doc_exclude_globs": doc_exclude_globs,
        "doc_audit_exclude_globs": doc_audit_exclude_globs,
        "docs_enabled": docs_enabled,
        # Legacy alias: non-empty only when old doc_paths style was used as prefixes.
        "doc_paths": legacy_paths if legacy_paths and docs_enabled else [],
        "sources": sources,
        "layered_ignore_globs": layered_globs,
        "layered_ignore_sources": layered_sources,
        "layered_reinclude_globs": layered_reinclude,
    }
