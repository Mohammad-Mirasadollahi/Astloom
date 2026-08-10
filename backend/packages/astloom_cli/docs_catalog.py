"""Documentation catalog: frontmatter index + on-disk cache.

Vocabularies (tags, lanes, doc_type, phase, …) are **observed from scanned
Markdown**, never a hardcoded product-wide enum. Each software tree can use its
own values. Closed-set Astloom lanes (procedure 09) remain a separate authoring
gate via docs-standards — not this catalog.

Does **not** invent ``DOCUMENTED_BY`` edges — evidence + sync remain required.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter

SCHEMA_VERSION = "1.1"
# Catalog may index tooling docs; Full-tier sync gate uses FULL_TIER_DOC_ROOTS.
DEFAULT_ROOTS: tuple[str, ...] = (
    "docs",
    "backend/docs",
    "frontend/docs",
    "ai-toolstack/docs",
    "deploy-toolkit",
)
CACHE_REL = Path(".astloom") / "cache" / "docs-catalog.json"

# Frontmatter keys whose *values* are collected into observed vocabularies.
_VOCAB_SCALAR_KEYS: tuple[str, ...] = (
    "lifecycle_lane",
    "concern_lane",
    "authority",
    "visibility",
    "doc_type",
    "phase",
    "status",
)
_VOCAB_LIST_KEYS: tuple[str, ...] = (
    "audience_lane",
    "tags",
)


def cache_path(repo: Path) -> Path:
    override = os.environ.get("ASTLOOM_DOCS_CATALOG_CACHE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    from astloom_cli.data_root import cache_dir

    return (cache_dir(install_root=repo) / "docs-catalog.json").resolve()


def resolve_catalog_roots(
    roots: tuple[str, ...] | list[str] | None = None,
) -> tuple[str, ...]:
    """CLI/MCP roots win; else env ``ASTLOOM_DOCS_CATALOG_ROOTS``; else defaults."""
    if roots is not None:
        cleaned = tuple(r.strip().replace("\\", "/").strip("/") for r in roots if str(r).strip())
        return cleaned or DEFAULT_ROOTS
    env = os.environ.get("ASTLOOM_DOCS_CATALOG_ROOTS", "").strip()
    if env:
        parts = tuple(p.strip().replace("\\", "/").strip("/") for p in env.split(",") if p.strip())
        if parts:
            return parts
    return DEFAULT_ROOTS


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                out.append(text)
        return out
    return []


def _truncate(text: str, *, max_chars: int = 240) -> str:
    body = " ".join((text or "").split())
    if len(body) <= max_chars:
        return body
    return body[: max_chars - 1].rstrip() + "…"


def _scan_roots(repo: Path, roots: tuple[str, ...] | list[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for rel in roots:
        root = (repo / rel).resolve()
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            parts = set(path.parts)
            if "node_modules" in parts or ".venv" in parts:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(resolved)
    return files


def _entry_from_markdown(repo: Path, path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fm, _body = parse_markdown_frontmatter(text)
    if not fm:
        return None
    rel = str(path.relative_to(repo)).replace("\\", "/")
    tags = _as_str_list(fm.get("tags"))
    linked = _as_str_list(fm.get("linked_symbols"))
    audience = _as_str_list(fm.get("audience_lane"))
    return {
        "path": rel,
        "doc_id": str(fm.get("doc_id") or "").strip(),
        "title": str(fm.get("title") or "").strip(),
        "summary": _truncate(str(fm.get("summary") or "")),
        "tags": tags,
        "doc_type": str(fm.get("doc_type") or "").strip(),
        "phase": str(fm.get("phase") or "").strip(),
        "status": str(fm.get("status") or "").strip(),
        "lifecycle_lane": str(fm.get("lifecycle_lane") or "").strip(),
        "concern_lane": str(fm.get("concern_lane") or "").strip(),
        "audience_lane": audience,
        "authority": str(fm.get("authority") or "").strip(),
        "visibility": str(fm.get("visibility") or "").strip(),
        "linked_symbols_count": len(linked),
        "has_linked_symbols": bool(linked),
    }


def _observed_vocabularies(documents: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Build vocabularies solely from values present in scanned frontmatter."""
    counters: dict[str, Counter[str]] = {key: Counter() for key in _VOCAB_SCALAR_KEYS}
    counters["audience_lane"] = Counter()
    counters["tags"] = Counter()
    for row in documents:
        for key in _VOCAB_SCALAR_KEYS:
            value = str(row.get(key) or "").strip()
            if value:
                counters[key][value] += 1
        for key in _VOCAB_LIST_KEYS:
            for value in row.get(key) or []:
                text = str(value or "").strip()
                if text:
                    counters[key][text] += 1
    return {
        key: [name for name, _count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]
        for key, counter in counters.items()
        if counter
    }


def build_docs_catalog(
    repo: Path,
    *,
    roots: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    """Scan Markdown trees and build a compact catalog from **observed** metadata."""
    use_roots = resolve_catalog_roots(roots)
    documents: list[dict[str, Any]] = []
    for path in _scan_roots(repo, use_roots):
        entry = _entry_from_markdown(repo, path)
        if entry is None:
            continue
        documents.append(entry)
    documents.sort(key=lambda row: (row.get("path") or ""))
    vocabularies = _observed_vocabularies(documents)
    tag_counts = Counter()
    for row in documents:
        for tag in row.get("tags") or []:
            tag_counts[str(tag)] += 1
    tags_sorted = sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    # lane_enums kept as alias of observed lane-like keys for callers that expect the name.
    lane_enums = {
        key: list(vocabularies.get(key) or [])
        for key in (
            "lifecycle_lane",
            "concern_lane",
            "audience_lane",
            "authority",
            "visibility",
        )
        if vocabularies.get(key)
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "docs_catalog",
        "generated_at": _now_iso(),
        "repo": str(repo.resolve()),
        "roots": list(use_roots),
        "vocabulary_source": "observed_frontmatter",
        "vocabularies": vocabularies,
        "lane_enums": lane_enums,
        "invents_edges": False,
        "note": (
            "Vocabularies are observed from this software's scanned docs — not a global hardcoded list. "
            "Use them to narrow which Markdown to Read. "
            "DOCUMENTED_BY still requires evidence linked_symbols + astloom sync."
        ),
        "stats": {
            "document_count": len(documents),
            "with_frontmatter": len(documents),
            "with_linked_symbols": sum(1 for d in documents if d.get("has_linked_symbols")),
            "unique_tags": len(tag_counts),
            "vocabulary_keys": sorted(vocabularies.keys()),
        },
        "tags": [{"tag": t, "count": c} for t, c in tags_sorted],
        "documents": documents,
    }


def save_docs_catalog_cache(repo: Path, catalog: dict[str, Any] | None = None) -> Path:
    payload = catalog if catalog is not None else build_docs_catalog(repo)
    path = cache_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def load_docs_catalog_cache(repo: Path) -> dict[str, Any] | None:
    path = cache_path(repo)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return None
    return data


def get_docs_catalog(
    repo: Path,
    *,
    refresh: bool = False,
    roots: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    """Return catalog from cache unless refresh or missing/stale schema."""
    if not refresh and roots is None:
        cached = load_docs_catalog_cache(repo)
        if cached is not None:
            cached = dict(cached)
            cached["cache_hit"] = True
            cached["cache_path"] = str(cache_path(repo))
            return cached
    catalog = build_docs_catalog(repo, roots=roots)
    save_docs_catalog_cache(repo, catalog)
    catalog = dict(catalog)
    catalog["cache_hit"] = False
    catalog["cache_path"] = str(cache_path(repo))
    return catalog


def refresh_docs_catalog_after_sync(
    repo: Path,
    *,
    roots: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    """Rebuild catalog cache (used at the **start** of ``astloom sync``; best-effort)."""
    catalog = get_docs_catalog(repo, refresh=True, roots=roots)
    stats = catalog.get("stats") or {}
    return {
        "ok": True,
        "cache_path": catalog.get("cache_path"),
        "document_count": int(stats.get("document_count") or 0),
        "unique_tags": int(stats.get("unique_tags") or 0),
        "roots": list(catalog.get("roots") or []),
        "vocabulary_source": catalog.get("vocabulary_source"),
        "schema_version": catalog.get("schema_version"),
    }

def filter_docs_catalog(
    catalog: dict[str, Any],
    *,
    tag: str = "",
    concern_lane: str = "",
    lifecycle_lane: str = "",
    audience_lane: str = "",
    phase: str = "",
    doc_type: str = "",
    query: str = "",
    has_linked_symbols: bool | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Filter catalog documents; returns observed vocabularies + tag list."""
    tag_f = tag.strip().casefold()
    concern_f = concern_lane.strip().casefold()
    life_f = lifecycle_lane.strip().casefold()
    aud_f = audience_lane.strip().casefold()
    phase_f = phase.strip().casefold()
    type_f = doc_type.strip().casefold()
    q = query.strip().casefold()
    lim = max(1, min(int(limit or 50), 500))

    matched: list[dict[str, Any]] = []
    for row in catalog.get("documents") or []:
        if not isinstance(row, dict):
            continue
        if tag_f and tag_f not in {t.casefold() for t in (row.get("tags") or [])}:
            continue
        if concern_f and str(row.get("concern_lane") or "").casefold() != concern_f:
            continue
        if life_f and str(row.get("lifecycle_lane") or "").casefold() != life_f:
            continue
        if aud_f and aud_f not in {a.casefold() for a in (row.get("audience_lane") or [])}:
            continue
        if phase_f and str(row.get("phase") or "").casefold() != phase_f:
            continue
        if type_f and str(row.get("doc_type") or "").casefold() != type_f:
            continue
        if has_linked_symbols is not None and bool(row.get("has_linked_symbols")) is not has_linked_symbols:
            continue
        if q:
            hay = " ".join(
                [
                    str(row.get("path") or ""),
                    str(row.get("doc_id") or ""),
                    str(row.get("title") or ""),
                    str(row.get("summary") or ""),
                    " ".join(row.get("tags") or []),
                    str(row.get("phase") or ""),
                    str(row.get("concern_lane") or ""),
                ]
            ).casefold()
            # Multi-word queries: every token must appear (AND), not the whole phrase.
            tokens = [t for t in q.split() if t]
            if tokens:
                if not all(t in hay for t in tokens):
                    continue
            elif q not in hay:
                continue
        matched.append(row)
        if len(matched) >= lim:
            break

    vocabularies = catalog.get("vocabularies") or _observed_vocabularies(
        [r for r in (catalog.get("documents") or []) if isinstance(r, dict)]
    )
    lane_enums = catalog.get("lane_enums") or {
        key: list(vocabularies.get(key) or [])
        for key in (
            "lifecycle_lane",
            "concern_lane",
            "audience_lane",
            "authority",
            "visibility",
        )
        if vocabularies.get(key)
    }

    return {
        "schema_version": catalog.get("schema_version") or SCHEMA_VERSION,
        "mode": "docs_catalog_query",
        "invents_edges": False,
        "vocabulary_source": catalog.get("vocabulary_source") or "observed_frontmatter",
        "note": catalog.get("note"),
        "cache_hit": catalog.get("cache_hit"),
        "cache_path": catalog.get("cache_path"),
        "generated_at": catalog.get("generated_at"),
        "roots": catalog.get("roots"),
        "vocabularies": vocabularies,
        "lane_enums": lane_enums,
        "tags": catalog.get("tags") or [],
        "stats": catalog.get("stats") or {},
        "filters": {
            "tag": tag or None,
            "concern_lane": concern_lane or None,
            "lifecycle_lane": lifecycle_lane or None,
            "audience_lane": audience_lane or None,
            "phase": phase or None,
            "doc_type": doc_type or None,
            "query": query or None,
            "has_linked_symbols": has_linked_symbols,
            "limit": lim,
        },
        "match_count": len(matched),
        "documents": matched,
    }
