"""Human Markdown → code-graph DOCUMENTATION nodes + DOCUMENTED_BY edges.

Role: project human docs as ``doc:human:{project}:{doc_id}`` and link only tokens
that resolve to existing code symbols.
Source of truth: Neo4j/store symbols and DOCUMENTED_BY edges; body hash is
``digest(body)`` (same as Phase 2 queue classification).
Allowed: skip re-embed when body hash unchanged; still refresh edges so newly
resolved tokens can link. Prune stale human DOCUMENTED_BY via filtered
``list_edges(rel_type, target_id)`` — never full-graph scan. Forbidden: invent
edges for unresolved tokens; fail the whole sync on one bad doc (callers
soft-fail per file).
"""

from __future__ import annotations

from typing import Any

from ...domain.enums import DocStatus, RelType, SymbolKind
from ...domain.errors import ValidationError
from ...domain.hashing import digest, now_iso
from ...domain.models import GraphSymbol, Scope
from ...domain.symbol_resolve import resolve_linked_symbol


def human_doc_symbol_id(project_id: str, doc_id: str) -> str:
    return f"doc:human:{project_id}:{doc_id}"


class HumanDocIngestMixin:
    """Project human Markdown docs as DOCUMENTATION nodes with DOCUMENTED_BY edges."""

    def upsert_human_documentation(
        self,
        scope: Scope,
        *,
        doc_id: str,
        relative_path: str,
        body: str,
        title: str = "",
        linked_symbol_tokens: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Upsert ``doc:human:{project}:{doc_id}`` and edge resolved code symbols.

        Only tokens that resolve to existing code symbols create ``DOCUMENTED_BY``
        edges (code → human doc). Unresolved tokens are reported, never invented.
        When an existing human doc has the same body hash, skip re-embed and
        symbol rewrite; still refresh edges (resolution may newly succeed).
        """
        doc_id = str(doc_id or "").strip()
        relative_path = str(relative_path or "").strip().replace("\\", "/")
        body = body if isinstance(body, str) else str(body or "")
        if not doc_id or not relative_path:
            raise ValidationError("doc_id and relative_path are required")

        stamp = now_iso()
        symbol_id = human_doc_symbol_id(scope.project_id, doc_id)
        previous = self._maybe_get(symbol_id, scope)
        body_hash = digest(body)
        content_unchanged = (
            previous is not None and str(previous.hash_value or "") == body_hash
        )
        if content_unchanged:
            doc_symbol = previous
        else:
            embed = self.embeddings.embed(f"{title or doc_id}\n{body[:2000]}")
            doc_symbol = GraphSymbol(
                id=symbol_id,
                scope=scope,
                kind=SymbolKind.DOCUMENTATION,
                file_path=relative_path,
                name=(
                    f"{title or doc_id}.md"
                    if not relative_path.endswith(".md")
                    else relative_path.rsplit("/", 1)[-1]
                ),
                qualified_name=f"human:{doc_id}",
                signature=title or doc_id,
                body=body,
                hash_value=body_hash,
                ai_documentation=body[:4000],
                doc_status=DocStatus.HUMAN,
                embedding=embed.vector,
                version=(previous.version + 1) if previous else 1,
                created_at=previous.created_at if previous else stamp,
                updated_at=stamp,
                language="",
            )
            self.store.put_symbol(doc_symbol)
            self._index_embedding(
                scope, symbol_id, embed.vector, kind=SymbolKind.DOCUMENTATION.value
            )

        linked: list[str] = []
        unresolved: list[str] = []
        edges = 0
        for token in linked_symbol_tokens or []:
            text = str(token or "").strip()
            if not text:
                continue
            target = resolve_linked_symbol(self.store, scope, text)
            if target is None:
                unresolved.append(text)
                continue
            edges += self._put_edge(
                scope,
                RelType.DOCUMENTED_BY.value,
                target.id,
                symbol_id,
                file_path=relative_path,
                metadata={"doc_id": doc_id, "origin": "human", **(metadata or {})},
                link_key=f"human:{doc_id}:{target.id}",
            )
            linked.append(target.id)

        linked_set = set(linked)
        removed = 0
        for edge in self.store.list_edges(
            scope,
            rel_type=RelType.DOCUMENTED_BY.value,
            target_id=symbol_id,
        ):
            if edge.metadata.get("origin") != "human":
                continue
            if edge.metadata.get("doc_id") != doc_id:
                continue
            if edge.source_id in linked_set:
                continue
            self.store.delete_edge(scope, edge.id)
            removed += 1

        return {
            "doc_symbol_id": symbol_id,
            "doc_id": doc_id,
            "relative_path": relative_path,
            "linked_symbol_ids": linked,
            "unresolved_tokens": unresolved,
            "edges_written": edges,
            "edges_removed": removed,
            "content_unchanged": content_unchanged,
        }
