"""Single-pass discovery of code + docs for inventory (avoid walking twice)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from code_graph_service.domain.doc_discovery import DOC_EXTENSIONS, DiscoveredDocFile
from code_graph_service.domain.languages import detect_language_from_path
from code_graph_service.domain.repo_discovery import (
    DEFAULT_MAX_FILE_BYTES,
    DiscoveredFile,
    _matches_any_glob,
    _matches_include,
    _normalize_extensions,
    _should_skip_parents,
    _split_excludes,
    iter_repo_files,
    path_matches_glob,
)


def discover_code_and_docs(
    root_path: Path,
    *,
    filters: dict[str, Any],
    max_files: int = 2000,
) -> tuple[list[DiscoveredFile], list[DiscoveredDocFile]]:
    """One pruned walk → code files and documentation files."""
    root = root_path.expanduser().resolve()
    max_files = max(1, min(int(max_files), 20_000))
    max_file_bytes = DEFAULT_MAX_FILE_BYTES

    code_excluded, code_globs = _split_excludes(filters.get("exclude_dirs"), filters.get("exclude_globs"))
    docs_enabled = bool(filters.get("docs_enabled")) and bool(filters.get("doc_match_globs"))
    doc_excluded, doc_globs = _split_excludes(
        filters.get("doc_exclude_dirs"),
        filters.get("doc_exclude_globs"),
    )
    # Prune using the union so neither pass descends into known-junk trees.
    walk_excluded = set(code_excluded) | set(doc_excluded)
    walk_globs = list(dict.fromkeys([*code_globs, *doc_globs]))

    extensions = _normalize_extensions(filters.get("include_extensions"))
    include_patterns = [str(p).strip().replace("\\", "/") for p in (filters.get("include_paths") or []) if str(p).strip()]
    match_globs = [str(p).strip() for p in (filters.get("doc_match_globs") or []) if str(p).strip()]
    doc_paths = [
        str(p).strip().replace("\\", "/").lstrip("./").rstrip("/")
        for p in (filters.get("doc_paths") or [])
        if str(p or "").strip()
    ]

    code: list[DiscoveredFile] = []
    docs: list[DiscoveredDocFile] = []
    for path, rel_s in iter_repo_files(root, exclude_dirs=walk_excluded, exclude_globs=walk_globs):
        relative = Path(rel_s)
        name_lower = path.name.lower()
        suffix = path.suffix.lower()

        if any(name_lower.endswith(ext) for ext in extensions):
            if not (code_globs and _matches_any_glob(rel_s, code_globs)):
                if not include_patterns or _matches_include(relative, include_patterns):
                    if not _should_skip_parents(relative, code_excluded):
                        language = detect_language_from_path(rel_s)
                        if language is not None:
                            try:
                                size = path.stat().st_size
                            except OSError:
                                size = 0
                            if 0 < size <= max_file_bytes:
                                code.append(
                                    DiscoveredFile(
                                        absolute_path=str(path),
                                        relative_path=rel_s,
                                        language=language,
                                        size_bytes=size,
                                    )
                                )

        if docs_enabled and suffix in DOC_EXTENSIONS and len(docs) < max_files:
            if not (doc_globs and _matches_any_glob(rel_s, doc_globs)):
                if not doc_paths or any(rel_s == p or rel_s.startswith(p + "/") for p in doc_paths):
                    if match_globs and any(path_matches_glob(rel_s, pat) for pat in match_globs):
                        if not _should_skip_parents(relative, doc_excluded):
                            try:
                                size = path.stat().st_size
                            except OSError:
                                size = 0
                            if 0 < size <= max_file_bytes:
                                docs.append(
                                    DiscoveredDocFile(
                                        absolute_path=str(path),
                                        relative_path=rel_s,
                                        size_bytes=size,
                                    )
                                )

        if len(code) >= max_files and (not docs_enabled or len(docs) >= max_files):
            break

    code.sort(key=lambda item: item.relative_path)
    docs.sort(key=lambda item: item.relative_path)
    return code[:max_files], docs[:max_files]
