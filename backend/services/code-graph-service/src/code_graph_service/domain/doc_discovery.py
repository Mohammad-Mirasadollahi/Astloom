"""Discover human documentation Markdown via match globs + docs-only excludes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .fs_paths import require_directory
from .repo_discovery import (
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_FILES,
    _matches_any_glob,
    _normalize_glob,
    _should_skip_parents,
    _split_excludes,
    iter_repo_files,
    path_matches_glob,
)

DOC_EXTENSIONS: frozenset[str] = frozenset({".md", ".mdx"})
DEFAULT_DOC_MATCH_GLOBS: tuple[str, ...] = ("**/*.md", "**/*.mdx")
# Kept for callers that still pass legacy doc_paths; prefer match globs.
DEFAULT_DOC_PATHS: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveredDocFile:
    """One Markdown file eligible for human-doc ingest."""

    absolute_path: str
    relative_path: str
    size_bytes: int


def _normalize_globs(patterns: Iterable[str] | None, *, default: tuple[str, ...]) -> list[str]:
    if patterns is None:
        raw = list(default)
    else:
        raw = list(patterns)
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = _normalize_glob(str(item or ""))
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def literal_dir_prefixes(match_globs: Iterable[str]) -> list[str] | None:
    """Static directory prefixes before the first glob metachar, or None = full-tree walk.

    Example: ``docs/**/*.md`` → ``["docs"]``. A pattern like ``**/*.md`` returns None.
    """
    prefixes: list[str] = []
    for raw in match_globs:
        pat = _normalize_glob(str(raw or ""))
        if not pat:
            continue
        parts: list[str] = []
        for part in pat.split("/"):
            if any(ch in part for ch in "*?["):
                break
            if part in ("", "."):
                continue
            parts.append(part)
        if not parts:
            return None
        prefixes.append("/".join(parts))
    if not prefixes:
        return None
    return list(dict.fromkeys(prefixes))


def discover_documentation_files(
    root_path: str | Path,
    *,
    match_globs: Iterable[str] | None = None,
    exclude_dirs: Iterable[str] | None = None,
    exclude_globs: Iterable[str] | None = None,
    doc_paths: Iterable[str] | None = None,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    deadline_monotonic: float | None = None,
) -> list[DiscoveredDocFile]:
    """Walk the repo and return Markdown files matching docs globs.

    Discovery is **exclude-only** after match: default ``match_globs`` is
    ``**/*.md`` and ``**/*.mdx`` over the whole tree. ``doc_paths`` (legacy) only
    narrows matches to those prefixes when provided and non-empty.

    When every match glob has a static directory prefix (e.g. ``docs/**/*.md``),
    only those subtrees are walked — critical over slow mounts (sshfs).
    """
    import time

    root = require_directory(root_path)

    matches = _normalize_globs(match_globs, default=DEFAULT_DOC_MATCH_GLOBS)
    if not matches:
        return []

    prefixes = [
        str(p).strip().replace("\\", "/").lstrip("./").rstrip("/")
        for p in (doc_paths or [])
        if str(p or "").strip()
    ]

    max_files = max(1, min(int(max_files), 20_000))
    max_file_bytes = max(1, int(max_file_bytes))
    excluded, globs = _split_excludes(exclude_dirs, exclude_globs)

    dir_prefixes = literal_dir_prefixes(matches)
    walk_specs: list[tuple[Path, str]] = []
    if dir_prefixes is None:
        walk_specs = [(root, "")]
    else:
        for pref in dir_prefixes:
            candidate = root / pref
            if candidate.is_dir():
                walk_specs.append((candidate, pref))

    discovered: list[DiscoveredDocFile] = []
    for walk_root, pref in walk_specs:
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            break
        for path, rel_in_walk in iter_repo_files(
            walk_root,
            exclude_dirs=excluded,
            exclude_globs=globs,
            deadline_monotonic=deadline_monotonic,
        ):
            rel_s = f"{pref}/{rel_in_walk}" if pref else rel_in_walk
            if path.suffix.lower() not in DOC_EXTENSIONS:
                continue
            if globs and _matches_any_glob(rel_s, globs):
                continue
            if prefixes and not any(rel_s == p or rel_s.startswith(p + "/") for p in prefixes):
                continue
            if not any(path_matches_glob(rel_s, pat) for pat in matches):
                continue
            relative = Path(rel_s)
            if _should_skip_parents(relative, excluded):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size <= 0 or size > max_file_bytes:
                continue
            discovered.append(
                DiscoveredDocFile(
                    absolute_path=str(path),
                    relative_path=rel_s,
                    size_bytes=size,
                )
            )
            if len(discovered) >= max_files:
                discovered.sort(key=lambda item: item.relative_path)
                return discovered

    discovered.sort(key=lambda item: item.relative_path)
    return discovered


__all__ = [
    "DEFAULT_DOC_MATCH_GLOBS",
    "DEFAULT_DOC_PATHS",
    "DOC_EXTENSIONS",
    "DiscoveredDocFile",
    "discover_documentation_files",
    "literal_dir_prefixes",
]
