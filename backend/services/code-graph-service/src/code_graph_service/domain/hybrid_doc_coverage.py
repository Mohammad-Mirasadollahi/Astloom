"""Hybrid documentation coverage pack for a code symbol.

Layers (any missing layer is covered by lower-priority layers):

- ``ast`` — always true after Phase 1 ingest for an ingested seed (neighbors / structure).
- ``living`` — heuristic/LLM ``ai_documentation`` on the symbol and/or living ``DOCUMENTED_BY`` docs.
- ``human`` — human Markdown as ``doc:human:…`` via resolved ``linked_symbols`` (Phase 2).
- ``rationale`` — optional ``# WHY:`` / ``NOTE:`` / ``HACK:`` rationale nodes (file or symbol).

**Optional (not required for hybrid to work):**

- Human Markdown / ``linked_symbols`` — if absent, prefer living then rationale then AST.
- Living LLM docs — if LLM/heuristic did not fill ``ai_documentation``, AST (+ rationale) still cover.
- Rationale tags — optional enrichment; never required.
- Embedding/LLM free-form doc↔symbol pairing — **not** used to invent graph edges (see product doc).

Never invents graph edges. Read-only merge for agents (``generation_context``).
"""

from __future__ import annotations

from typing import Any, Protocol

from .enums import DocStatus, RelType, SymbolKind
from .errors import NotFoundError
from .models import GraphSymbol, Scope

# Preference order for prompt snippets (first present wins).
FALLBACK_CHAIN: tuple[str, ...] = ("human", "living", "rationale", "ast")


class _SymbolStore(Protocol):
    def get_symbol(self, symbol_id: str, scope: Scope) -> GraphSymbol: ...

    def list_edges(self, scope: Scope) -> list[Any]: ...


_AST_REL_TYPES = frozenset(
    {
        RelType.CONTAINS.value,
        RelType.CALLS.value,
        RelType.IMPORTS.value,
        RelType.INHERITS_FROM.value,
        RelType.ROUTES_TO.value,
        RelType.TESTED_BY.value,
        RelType.HTTP_CALLS.value,
        RelType.ASYNC_CALLS.value,
    }
)


def _snippet(text: str, *, max_chars: int = 500) -> str:
    body = (text or "").strip()
    if len(body) <= max_chars:
        return body
    return body[: max_chars - 1].rstrip() + "…"


def _doc_view(symbol: GraphSymbol, *, origin: str) -> dict[str, Any]:
    return {
        "symbol_id": symbol.id,
        "origin": origin,
        "kind": symbol.kind.value,
        "qualified_name": symbol.qualified_name,
        "file_path": symbol.file_path,
        "doc_status": symbol.doc_status.value,
        "title": symbol.signature or symbol.name,
        "snippet": _snippet(symbol.ai_documentation or symbol.body or ""),
    }


def _dedupe_docs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("symbol_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def build_symbol_doc_coverage(
    store: _SymbolStore,
    scope: Scope,
    seed: GraphSymbol,
    *,
    max_neighbors: int = 12,
    max_snippets: int = 5,
) -> dict[str, Any]:
    """Return layered hybrid coverage for ``seed`` (AST + living + human + rationale)."""
    living_docs: list[dict[str, Any]] = []
    human_docs: list[dict[str, Any]] = []
    rationale: list[dict[str, Any]] = []
    ast_neighbors: list[dict[str, Any]] = []

    if (seed.ai_documentation or "").strip() and seed.kind not in {
        SymbolKind.DOCUMENTATION,
        SymbolKind.RATIONALE,
        SymbolKind.FILE,
        SymbolKind.UNRESOLVED,
        SymbolKind.EXTERNAL,
    }:
        living_docs.append(
            {
                "symbol_id": seed.id,
                "origin": "living_inline",
                "kind": seed.kind.value,
                "qualified_name": seed.qualified_name,
                "file_path": seed.file_path,
                "doc_status": seed.doc_status.value,
                "title": seed.signature or seed.name,
                "snippet": _snippet(seed.ai_documentation),
            }
        )

    file_id = f"file:{scope.project_id}:{seed.file_path}"
    seen_neighbor_ids: set[str] = set()

    for edge in store.list_edges(scope):
        rel = str(getattr(edge, "rel_type", "") or "")
        source_id = str(getattr(edge, "source_id", "") or "")
        target_id = str(getattr(edge, "target_id", "") or "")
        meta = getattr(edge, "metadata", None) or {}

        # DOCUMENTED_BY: code → documentation / rationale
        if rel == RelType.DOCUMENTED_BY.value and source_id == seed.id:
            try:
                doc = store.get_symbol(target_id, scope)
            except NotFoundError:
                continue
            if doc.kind == SymbolKind.RATIONALE:
                rationale.append(_doc_view(doc, origin="rationale"))
                continue
            if doc.kind != SymbolKind.DOCUMENTATION:
                continue
            origin = str(meta.get("origin") or "")
            if (
                origin in {"human", "package_readme"}
                or doc.id.startswith("doc:human:")
                or doc.doc_status == DocStatus.HUMAN
            ):
                human_docs.append(_doc_view(doc, origin="human" if origin != "package_readme" else "package_readme"))
            else:
                living_docs.append(_doc_view(doc, origin="living"))
            continue

        # Optional: rationale / package README linked from FILE → doc
        if rel == RelType.DOCUMENTED_BY.value and source_id == file_id:
            try:
                doc = store.get_symbol(target_id, scope)
            except NotFoundError:
                continue
            if doc.kind == SymbolKind.RATIONALE:
                rationale.append(_doc_view(doc, origin="rationale"))
            elif doc.kind == SymbolKind.DOCUMENTATION:
                origin = str(meta.get("origin") or "")
                if (
                    origin in {"human", "package_readme"}
                    or doc.id.startswith("doc:human:")
                    or doc.doc_status == DocStatus.HUMAN
                ):
                    human_docs.append(
                        _doc_view(
                            doc,
                            origin="package_readme" if origin == "package_readme" else "human",
                        )
                    )
            continue

        if rel not in _AST_REL_TYPES:
            continue
        other = target_id if source_id == seed.id else source_id if target_id == seed.id else ""
        if not other or other == seed.id or other in seen_neighbor_ids:
            continue
        try:
            neighbor = store.get_symbol(other, scope)
        except NotFoundError:
            continue
        if neighbor.kind in {
            SymbolKind.FILE,
            SymbolKind.UNRESOLVED,
            SymbolKind.EXTERNAL,
            SymbolKind.DOCUMENTATION,
            SymbolKind.RATIONALE,
        }:
            continue
        seen_neighbor_ids.add(other)
        if len(ast_neighbors) < max_neighbors:
            ast_neighbors.append(
                {
                    "symbol_id": neighbor.id,
                    "rel_type": rel,
                    "kind": neighbor.kind.value,
                    "qualified_name": neighbor.qualified_name,
                    "file_path": neighbor.file_path,
                    "signature": neighbor.signature,
                }
            )

    living_docs = _dedupe_docs(living_docs)
    human_docs = _dedupe_docs(human_docs)
    rationale = _dedupe_docs(rationale)

    coverage = {
        "ast": True,
        "living": bool(living_docs),
        "human": bool(human_docs),
        "rationale": bool(rationale),
    }
    active = [name for name in FALLBACK_CHAIN if coverage.get(name)]
    preferred = next((name for name in FALLBACK_CHAIN if coverage.get(name)), "ast")
    gaps = [name for name in FALLBACK_CHAIN if name != "ast" and not coverage.get(name)]

    preferred_snippets: list[str] = []
    if preferred == "human":
        preferred_snippets.extend(d["snippet"] for d in human_docs if d.get("snippet"))
    elif preferred == "living":
        preferred_snippets.extend(d["snippet"] for d in living_docs if d.get("snippet"))
    elif preferred == "rationale":
        preferred_snippets.extend(d["snippet"] for d in rationale if d.get("snippet"))

    optional_notes = {
        "human_docs": "Optional: add Full-tier Markdown + evidence linked_symbols, then astloom sync.",
        "living_docs": "Optional: enabled when ingest generates ai_documentation (heuristic or LLM).",
        "rationale": "Optional: add # WHY: / # NOTE: / # HACK: comments in source; re-ingest file.",
        "llm_auto_pair": (
            "Optional future: LLM may *suggest* links; never auto-writes DOCUMENTED_BY "
            "without evidence resolve. Use astloom docs-suggest-links for evidence tokens."
        ),
    }

    return {
        "mode": "hybrid",
        "seed_symbol_id": seed.id,
        "seed_qualified_name": seed.qualified_name,
        "seed_file_path": seed.file_path,
        "seed_kind": seed.kind.value,
        "coverage": coverage,
        "active_layers": active,
        "gaps": gaps,
        "fallback_chain": list(FALLBACK_CHAIN),
        "preferred_layer": preferred,
        "layers": {
            "ast_neighbors": ast_neighbors,
            "living_docs": living_docs,
            "human_docs": human_docs,
            "rationale": rationale,
        },
        "preferred_snippets": preferred_snippets[:max_snippets],
        "optional": optional_notes,
        "invents_edges": False,
    }
