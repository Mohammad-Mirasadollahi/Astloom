"""Surgical explore packing with adaptive budget (Wave 1 — CodeGraph-inspired)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

_CAMEL = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-zA-Z0-9]*)*|[a-z]+(?:[A-Z][a-zA-Z0-9]+)+)\b")
_SNAKE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b", re.IGNORECASE)
_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "how",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "does",
        "work",
        "flow",
        "reach",
        "through",
        "into",
        "code",
        "file",
        "function",
        "class",
        "method",
        "show",
        "explain",
        "about",
    }
)


@dataclass
class ExploreSymbol:
    id: str
    name: str
    qualified_name: str
    file_path: str
    signature: str
    body: str
    kind: str
    score: float = 0.0
    on_spine: bool = False
    sibling_group: str | None = None


@dataclass
class ExploreSection:
    file_path: str
    symbols: list[dict] = field(default_factory=list)
    skeletonized: bool = False


@dataclass
class ExplorePack:
    query: str
    budget_chars: int
    used_chars: int
    sections: list[ExploreSection]
    seed_ids: list[str]
    call_path_ids: list[str]
    notes: list[str] = field(default_factory=list)


def extract_query_terms(query: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for pattern in (_CAMEL, _SNAKE):
        for match in pattern.finditer(query):
            tok = match.group(1)
            key = tok.lower()
            if key in _STOP or len(tok) < 2 or key in seen:
                continue
            seen.add(key)
            terms.append(tok)
    for raw in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\b", query):
        key = raw.lower()
        if key in _STOP or key in seen:
            continue
        seen.add(key)
        terms.append(raw)
    return terms


def sibling_group_key(symbol: ExploreSymbol) -> str | None:
    """Group interchangeable impls: same file-stem suffix or Shared* base naming."""
    name = symbol.name
    # Interceptor / Handler / Service / Repository families
    for suffix in ("Interceptor", "Handler", "Service", "Repository", "Controller", "Middleware"):
        if name.endswith(suffix) and len(name) > len(suffix):
            return suffix
    if symbol.kind == "method" and "." in symbol.qualified_name:
        return symbol.qualified_name.rsplit(".", 1)[-1]
    return None


def explore_budget_for_file_count(file_count: int) -> int:
    """Adaptive ceiling scaled to project size (chars of emitted source)."""
    if file_count < 100:
        return 18_000
    if file_count < 500:
        return 24_000
    if file_count < 2000:
        return 28_000
    return 32_000


def build_explore_pack(
    query: str,
    symbols: Iterable[ExploreSymbol],
    *,
    call_path_ids: list[str] | None = None,
    file_count: int = 0,
    budget_chars: int | None = None,
) -> ExplorePack:
    """Pack symbols into file sections; skeletonize off-spine siblings under budget."""
    call_path_ids = call_path_ids or []
    spine = set(call_path_ids)
    budget = budget_chars if budget_chars is not None else explore_budget_for_file_count(file_count)
    items = list(symbols)
    for item in items:
        item.on_spine = item.id in spine
        item.sibling_group = sibling_group_key(item)

    # Count siblings per group (only groups with ≥3 members trigger skeletonization)
    group_counts: dict[str, int] = {}
    for item in items:
        if item.sibling_group:
            group_counts[item.sibling_group] = group_counts.get(item.sibling_group, 0) + 1

    # Prefer spine + higher score
    items.sort(key=lambda s: (0 if s.on_spine else 1, -s.score, s.file_path, s.qualified_name))

    by_file: dict[str, list[ExploreSymbol]] = {}
    for item in items:
        by_file.setdefault(item.file_path or "(unknown)", []).append(item)

    sections: list[ExploreSection] = []
    used = 0
    notes: list[str] = []
    emitted_ids: list[str] = []

    for file_path, file_syms in by_file.items():
        section = ExploreSection(file_path=file_path)
        # Keep at most one full body per sibling group (prefer spine)
        full_kept_for_group: set[str] = set()
        for sym in file_syms:
            group = sym.sibling_group
            large_family = bool(group and group_counts.get(group, 0) >= 3)
            has_spine_sibling = bool(
                group and any(s.on_spine and s.sibling_group == group for s in items)
            )

            if sym.on_spine:
                skeletonize = False
                if group:
                    full_kept_for_group.add(group)
            elif large_family and has_spine_sibling:
                skeletonize = True
            elif large_family and group and group not in full_kept_for_group:
                skeletonize = False
                full_kept_for_group.add(group)
            elif large_family and group in full_kept_for_group:
                skeletonize = True
            else:
                skeletonize = False

            if skeletonize:
                body = ""
                render = "signature"
                section.skeletonized = True
            else:
                body = sym.body or ""
                render = "full"
                if group:
                    full_kept_for_group.add(group)

            chunk = f"{sym.signature}\n{body}".strip()
            if used + len(chunk) > budget and render == "full" and body:
                # Collapse to signature to stay under budget
                body = ""
                render = "signature"
                section.skeletonized = True
                chunk = sym.signature
                notes.append(f"budget_collapse:{sym.qualified_name}")

            if used + len(chunk) > budget and not sym.on_spine:
                notes.append(f"omitted_over_budget:{sym.qualified_name}")
                continue

            section.symbols.append(
                {
                    "id": sym.id,
                    "name": sym.name,
                    "qualified_name": sym.qualified_name,
                    "kind": sym.kind,
                    "file_path": sym.file_path,
                    "signature": sym.signature,
                    "body": body,
                    "render": render,
                    "confidence_note": "bodies from indexed symbols; prefer exact CALLS edges",
                    "on_spine": sym.on_spine,
                    "score": sym.score,
                }
            )
            used += len(chunk)
            emitted_ids.append(sym.id)

        if section.symbols:
            sections.append(section)

    return ExplorePack(
        query=query,
        budget_chars=budget,
        used_chars=used,
        sections=sections,
        seed_ids=emitted_ids[:8],
        call_path_ids=call_path_ids,
        notes=notes,
    )
