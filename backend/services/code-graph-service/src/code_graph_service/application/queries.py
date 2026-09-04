"""Query use cases: symbol lookup, structural/semantic search, polyglot profile."""

from __future__ import annotations

from typing import Any

from ..domain.embeddings import cosine
from ..domain.errors import NotFoundError, ValidationError
from ..domain.impact import directed_impact, escalate_hint, rank_callers
from ..domain.models import GraphSymbol, Scope
from ..domain.polyglot_profile import PolyglotProjectProfile, build_polyglot_profile
from ..domain.ports import list_symbols_compact
from ..domain.rag import (
    DEFAULT_EXPAND_DEPTH,
    DEFAULT_EXPAND_EDGE_LIMIT,
    DEFAULT_EXPAND_SEEDS,
    SEARCHABLE_SYMBOL_KINDS,
)
from ..domain.unused_candidates import find_unused_candidates
from .support import GraphServiceSupport


class QueryUseCases(GraphServiceSupport):
    def get_symbol(self, scope: Scope, symbol_id: str) -> GraphSymbol:
        return self.store.get_symbol(symbol_id, scope)

    def _symbols_for_ids(self, scope: Scope, symbol_ids: set[str]) -> dict[str, GraphSymbol]:
        out: dict[str, GraphSymbol] = {}
        for sid in symbol_ids:
            if not sid:
                continue
            try:
                out[sid] = self.store.get_symbol(sid, scope)
            except NotFoundError:
                continue
        return out

    def unused_candidates(
        self,
        scope: Scope,
        *,
        scope_mode: str,
        anchor_symbols: list[str] | None = None,
        anchor_paths: list[str] | None = None,
        max_results: int = 50,
        include_uncertain: bool = False,
        min_confidence: float | None = None,
        coverage_hits: dict[str, int] | None = None,
        flag_states: dict[str, Any] | None = None,
        repo_root: str | None = None,
        disk_search: bool = False,
        path_prefix: str | None = None,
    ) -> dict[str, Any]:
        banner = (
            self.freshness_status(scope)
            if hasattr(self, "freshness_status")
            else {"pending_files": [], "is_stale": False}
        )
        pending = banner.get("pending_files") or banner.get("pending") or []
        pending_count = int(banner.get("pending_count") or len(pending) or 0)
        if pending:
            process_freshness = "pending_sync"
        elif banner.get("is_stale") or banner.get("stale"):
            process_freshness = "stale"
        else:
            process_freshness = "ok"
        durable = banner.get("last_sync_at")
        # CI-40: pending always fail-closed. Process-local unknown/stale after an
        # MCP restart must not wipe absence claims when a durable sync stamp exists.
        safe_absence = pending_count == 0 and (
            process_freshness == "ok" or bool(durable)
        )
        scoring_freshness = "ok" if safe_absence else process_freshness
        if not repo_root:
            env_root = str(__import__("os").environ.get("ASTLOOM_ROOT") or "").strip()
            repo_root = env_root or None
        symbols = list_symbols_compact(self.store, scope)
        try:
            payload = find_unused_candidates(
                symbols,
                self.store.list_edges(scope),
                scope_mode=scope_mode,
                anchor_symbols=anchor_symbols,
                anchor_paths=anchor_paths,
                max_results=max_results,
                include_uncertain=include_uncertain,
                freshness=scoring_freshness,
                min_confidence=min_confidence,
                coverage_hits=coverage_hits,
                flag_states=flag_states,
                repo_root=repo_root,
                disk_search=disk_search,
                path_prefix=path_prefix,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        payload["freshness"] = "ok" if safe_absence else process_freshness
        payload["freshness_detail"] = {
            "pending_files": pending if isinstance(pending, list) else [],
            "last_sync_at": durable,
            "process_status": banner.get("status"),
        }
        payload["index_coverage"] = {
            "status": "incomplete" if not safe_absence else "ok",
            "pending_count": pending_count,
            "safe_absence_claims": safe_absence,
            "note": (
                "Refuse safe_to_delete when index incomplete (CI-40); "
                "run astloom sync / check freshness before dead-code claims"
                if not safe_absence
                else (
                    "index looks fresh for scoped absence claims"
                    if process_freshness == "ok"
                    else "durable sync stamp present; process freshness not re-verified"
                )
            ),
        }
        # CI-40: never claim safe_to_delete when the index cannot support absence claims.
        if not safe_absence:
            demoted: list[dict[str, Any]] = []
            for row in payload.get("candidates") or []:
                moved = dict(row)
                moved["safe_to_delete"] = False
                blockers = list(moved.get("blockers") or [])
                blockers = list(dict.fromkeys([*blockers, "index_incomplete"]))
                moved["blockers"] = blockers
                demoted.append(moved)
            if demoted:
                skipped = list(payload.get("skipped_uncertain") or [])
                skipped = [
                    {
                        "symbol": r.get("symbol"),
                        "symbol_id": r.get("symbol_id"),
                        "path": r.get("path"),
                        "finding_kind": r.get("finding_kind"),
                        "score": r.get("score"),
                        "confidence": r.get("confidence"),
                        "test_only": r.get("test_only", False),
                        "evidence": r.get("evidence") or [],
                        "blockers": r.get("blockers") or [],
                    }
                    for r in demoted
                ] + skipped
                payload["candidates"] = []
                payload["skipped_uncertain"] = skipped[: max(1, min(int(max_results or 50), 200))]
            hints = dict(payload.get("kpi_hints") or {})
            hints["dead_code_candidates_surfaced"] = len(payload.get("candidates") or [])
            hints["dead_code_candidates_skipped_uncertain"] = len(
                payload.get("skipped_uncertain") or []
            )
            hints.setdefault("dead_code_candidates_resolved", 0)
            payload["kpi_hints"] = hints
        else:
            hints = dict(payload.get("kpi_hints") or {})
            hints.setdefault("dead_code_candidates_resolved", 0)
            payload["kpi_hints"] = hints
        return payload

    def get_polyglot_profile(self, scope: Scope) -> PolyglotProjectProfile:
        return build_polyglot_profile(
            list_symbols_compact(self.store, scope), self.store.list_edges(scope)
        )

    def structural_query(
        self,
        scope: Scope,
        symbol_id: str,
        rel_type: str | None = None,
        *,
        max_depth: int = 1,
    ) -> dict[str, Any]:
        symbol = self.store.get_symbol(symbol_id, scope)
        caps = getattr(self.store, "capabilities", None)
        cap_map = caps() if callable(caps) else {}
        fetch = getattr(self.store, "neighborhood_edges", None)
        edges = None
        expansion = "one_hop"
        if callable(fetch):
            rels = [rel_type.upper()] if rel_type else [
                "CALLS",
                "HTTP_CALLS",
                "ASYNC_CALLS",
                "ROUTES_TO",
                "IMPORTS",
                "INHERITS_FROM",
                "DOCUMENTED_BY",
                "TESTED_BY",
                "CONTAINS",
            ]
            try:
                edges = list(
                    fetch(
                        scope,
                        symbol_id,
                        max_depth=max_depth,
                        direction="both",
                        rel_types=rels,
                    )
                    or []
                )
                expansion = "cypher_neighborhood"
            except Exception:
                edges = None
        if edges is None:
            edges = [
                edge
                for edge in self.store.list_edges(scope)
                if edge.source_id == symbol_id or edge.target_id == symbol_id
            ]
            if rel_type:
                edges = [edge for edge in edges if edge.rel_type == rel_type.upper()]
            expansion = "one_hop"
        payload = {
            "symbol": self._symbol_view(symbol),
            "max_depth": max_depth,
            "expansion": expansion,
            "reference_kind": "structural",
            "edges": [
                {
                    "id": edge.id,
                    "rel_type": edge.rel_type,
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "confidence": edge.confidence.value,
                    "metadata": edge.metadata,
                }
                for edge in edges
            ],
        }
        rank = getattr(self.store, "rank_symbols_by_degree", None)
        if cap_map:
            payload["neo4j_capabilities"] = cap_map
        if callable(rank) and max_depth > 1:
            payload["importance_hints"] = rank(scope, top_k=8)
        payload["escalate_hint"] = escalate_hint(sparse=len(payload["edges"]) == 0)
        freshness_fn = getattr(self, "freshness_status", None)
        if callable(freshness_fn):
            payload["freshness"] = freshness_fn(scope)
        return payload

    def callers(
        self,
        scope: Scope,
        symbol_id: str,
        *,
        top_k: int = 20,
        max_depth: int = 1,
        min_confidence: str | None = "probable",
        rel_types: list[str] | None = None,
    ) -> dict[str, Any]:
        symbol = self.store.get_symbol(symbol_id, scope)
        allowed = frozenset(r.upper() for r in rel_types) if rel_types else None
        edges = self._structural_edges_for_seed(
            scope,
            symbol.id,
            max_depth=max_depth,
            direction="upstream",
            rel_types=list(allowed) if allowed else None,
        )
        symbols = self._symbols_for_ids(
            scope,
            {symbol.id, *(e.source_id for e in edges), *(e.target_id for e in edges)},
        )
        payload = rank_callers(
            symbol.id,
            symbols,
            edges,
            top_k=top_k,
            max_depth=max_depth,
            min_confidence=min_confidence,
            rel_types=allowed,
        )
        payload["symbol"] = self._symbol_view(symbol)
        freshness_fn = getattr(self, "freshness_status", None)
        if callable(freshness_fn):
            payload["freshness"] = freshness_fn(scope)
        return payload

    def impact_analysis(
        self,
        scope: Scope,
        symbol_id: str,
        *,
        direction: str = "both",
        max_depth: int = 3,
        min_confidence: str | None = "probable",
        rel_types: list[str] | None = None,
        top_k: int = 50,
        include_legacy_expand: bool = True,
    ) -> dict[str, Any]:
        symbol = self.store.get_symbol(symbol_id, scope)
        allowed = frozenset(r.upper() for r in rel_types) if rel_types else None
        edges = self._structural_edges_for_seed(
            scope,
            symbol.id,
            max_depth=max_depth,
            direction=direction,
            rel_types=list(allowed) if allowed else None,
        )
        symbols = self._symbols_for_ids(
            scope,
            {symbol.id, *(e.source_id for e in edges), *(e.target_id for e in edges)},
        )
        payload = directed_impact(
            symbol.id,
            symbols,
            edges,
            direction=direction,
            max_depth=max_depth,
            min_confidence=min_confidence,
            rel_types=allowed,
            top_k=top_k,
        )
        payload["symbol"] = self._symbol_view(symbol)
        if include_legacy_expand:
            legacy = self.structural_query(
                scope,
                symbol.id,
                None if not rel_types else rel_types[0],
                max_depth=max_depth,
            )
            payload["edges"] = legacy.get("edges") or []
            payload["expansion"] = legacy.get("expansion")
            if "importance_hints" in legacy:
                payload["importance_hints"] = legacy["importance_hints"]
            if "neo4j_capabilities" in legacy:
                payload["neo4j_capabilities"] = legacy["neo4j_capabilities"]
        freshness_fn = getattr(self, "freshness_status", None)
        if callable(freshness_fn):
            payload["freshness"] = freshness_fn(scope)
        return payload

    def _structural_edges_for_seed(
        self,
        scope: Scope,
        seed_id: str,
        *,
        max_depth: int,
        direction: str,
        rel_types: list[str] | None,
    ) -> list[Any]:
        """Prefer Neo4j Cypher neighborhood when available; else full in-memory edge list."""
        fetch = getattr(self.store, "neighborhood_edges", None)
        if callable(fetch):
            try:
                return list(
                    fetch(
                        scope,
                        seed_id,
                        max_depth=max_depth,
                        direction=direction,
                        rel_types=rel_types,
                    )
                    or []
                )
            except Exception:
                pass
        return list(self.store.list_edges(scope))

    def semantic_search(
        self,
        scope: Scope,
        query: str,
        top_k: int = 5,
        *,
        expand_seeds: int = DEFAULT_EXPAND_SEEDS,
        expand_depth: int = DEFAULT_EXPAND_DEPTH,
    ) -> list[dict[str, Any]]:
        """Stage-1 hybrid RAG: kind-filtered pgvector (or in-store) → optional TurboVec Stage-2 → Neo4j expand."""
        if not query.strip():
            raise ValidationError("query is required")
        top_k = max(1, top_k)
        expand_seeds = max(0, min(int(expand_seeds), top_k))
        expand_depth = max(1, min(int(expand_depth), 3))
        try:
            vector = self.embeddings.embed(query, is_query=True).vector
        except Exception as exc:  # noqa: BLE001 — lexical must still return
            hits = self._lexical_search_hits(scope, query, top_k)
            if hits:
                hits[0]["semantic_error"] = f"{type(exc).__name__}:{exc}"[:300]
            return hits

        hits: list[dict[str, Any]] = []
        retrieval = "in_store_cosine"
        candidate_pool = max(top_k * 4, top_k)
        if self.embedding_index is not None:
            retrieval = "pgvector"
            for symbol_id, score in self.embedding_index.search(
                scope,
                vector,
                top_k=candidate_pool,
                kinds=sorted(SEARCHABLE_SYMBOL_KINDS),
            ):
                try:
                    symbol = self.store.get_symbol(symbol_id, scope)
                except NotFoundError:
                    self._delete_embedding(scope, symbol_id)
                    continue
                if symbol.kind.value not in SEARCHABLE_SYMBOL_KINDS:
                    self._delete_embedding(scope, symbol_id)
                    continue
                hits.append(
                    {
                        "score": round(score, 6),
                        "symbol": self._symbol_view(symbol),
                        "retrieval": retrieval,
                    }
                )
        else:
            scored: list[tuple[float, GraphSymbol]] = []
            for symbol in self.store.list_symbols(scope):
                if symbol.kind.value not in SEARCHABLE_SYMBOL_KINDS:
                    continue
                scored.append((cosine(vector, symbol.embedding), symbol))
            scored.sort(key=lambda item: (-item[0], item[1].qualified_name))
            for score, symbol in scored[:candidate_pool]:
                if score <= 0:
                    continue
                hits.append(
                    {
                        "score": round(score, 6),
                        "symbol": self._symbol_view(symbol),
                        "retrieval": retrieval,
                    }
                )

        hits = self._maybe_turbovec_rerank(scope, vector, hits, top_k=top_k)

        self._attach_graph_neighbors(
            scope,
            hits,
            expand_seeds=expand_seeds,
            expand_depth=expand_depth,
        )
        return hits[:top_k]

    def _lexical_search_hits(
        self,
        scope: Scope,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        from ..domain.hybrid_search import lexical_rank, searchable_text

        fulltext = getattr(self.store, "fulltext_search", None)
        if callable(fulltext):
            try:
                rows = fulltext(scope, query, top_k=top_k)
            except Exception:
                rows = []
            hits: list[dict[str, Any]] = []
            for row in rows or []:
                sid = str(row.get("symbol_id") or "")
                if not sid:
                    continue
                try:
                    symbol = self.store.get_symbol(sid, scope)
                except NotFoundError:
                    continue
                hits.append(
                    {
                        "score": float(row.get("score") or 0.0),
                        "symbol": self._symbol_view(symbol),
                        "retrieval": "lexical_fallback",
                    }
                )
            if hits:
                return hits[:top_k]

        name_search = getattr(self.store, "symbol_name_search", None)
        if callable(name_search):
            try:
                rows = name_search(scope, query, top_k=top_k)
            except Exception:
                rows = []
            hits = []
            for row in rows or []:
                sid = str(row.get("symbol_id") or "")
                if not sid:
                    continue
                try:
                    symbol = self.store.get_symbol(sid, scope)
                except NotFoundError:
                    continue
                hits.append(
                    {
                        "score": 0.0,
                        "symbol": self._symbol_view(symbol),
                        "retrieval": "lexical_fallback",
                    }
                )
            if hits:
                return hits[:top_k]

        symbols = [
            s
            for s in list_symbols_compact(self.store, scope)
            if s.kind.value in SEARCHABLE_SYMBOL_KINDS
        ]
        corpus = [
            (
                s.id,
                searchable_text(
                    name=s.name,
                    qualified_name=s.qualified_name,
                    signature=s.signature or "",
                    file_path=s.file_path or "",
                    ai_documentation="",
                    body="",
                ),
            )
            for s in symbols
        ]
        ranked = lexical_rank(query, corpus, top_k=top_k)
        by_id = {s.id: s for s in symbols}
        hits: list[dict[str, Any]] = []
        for sid in ranked:
            sym = by_id.get(sid)
            if sym is None:
                continue
            hits.append(
                {
                    "score": 0.0,
                    "symbol": self._symbol_view(sym),
                    "retrieval": "lexical_fallback",
                }
            )
        return hits[:top_k]

    def _maybe_turbovec_rerank(
        self,
        scope: Scope,
        query_vector: list[float] | tuple[float, ...],
        hits: list[dict[str, Any]],
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Optional Stage-2 dense allowlist via injected VectorIndexPort + durable id map.

        Production path requires composition-root injection. Env-only hash id maps are not used
        (collision risk across projects). Fail open to Stage-1 hits when unbound or on error.
        """
        if not hits:
            return hits
        vector_index = getattr(self, "vector_index", None)
        entity_id_map = getattr(self, "entity_id_map", None)
        if vector_index is None or entity_id_map is None:
            return hits[:top_k]
        return self._stage2_allowlist_search(
            query_vector,
            hits,
            top_k=top_k,
            vector_index=vector_index,
            entity_id_map=entity_id_map,
        )

    def _stage2_allowlist_search(
        self,
        query_vector: list[float] | tuple[float, ...],
        hits: list[dict[str, Any]],
        *,
        top_k: int,
        vector_index: Any,
        entity_id_map: Any,
    ) -> list[dict[str, Any]]:
        allowlist: list[int] = []
        id_to_hit: dict[int, dict[str, Any]] = {}
        for hit in hits:
            sid = str((hit.get("symbol") or {}).get("id") or "")
            if not sid:
                continue
            uid = entity_id_map.to_uint64(sid)
            if uid is None:
                continue
            allowlist.append(int(uid))
            id_to_hit[int(uid)] = hit
        if not allowlist:
            return hits[:top_k]
        try:
            import numpy as np

            scores, hit_ids = vector_index.search(
                np.asarray(query_vector, dtype=np.float32),
                top_k,
                allowlist=allowlist,
            )
            return self._hits_from_ann_scores(scores, hit_ids, id_to_hit, hits, top_k=top_k)
        except Exception:
            return hits[:top_k]

    @staticmethod
    def _hits_from_ann_scores(
        scores: Any,
        hit_ids: Any,
        id_to_hit: dict[int, dict[str, Any]],
        fallback: list[dict[str, Any]],
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        reranked: list[dict[str, Any]] = []
        for score, uid in zip(list(scores), list(hit_ids), strict=False):
            hit = id_to_hit.get(int(uid))
            if not hit:
                continue
            updated = dict(hit)
            updated["score"] = round(float(score), 6)
            updated["retrieval"] = "turbovec"
            reranked.append(updated)
        return reranked or fallback[:top_k]

    def _attach_graph_neighbors(
        self,
        scope: Scope,
        hits: list[dict[str, Any]],
        *,
        expand_seeds: int,
        expand_depth: int,
    ) -> None:
        if not hits or expand_seeds <= 0:
            return
        expand = getattr(self.store, "expand_neighborhood", None)
        for hit in hits[:expand_seeds]:
            seed_id = str(hit["symbol"]["id"])
            if callable(expand):
                try:
                    graph_edges = expand(
                        scope,
                        seed_id,
                        max_depth=expand_depth,
                        limit=DEFAULT_EXPAND_EDGE_LIMIT,
                    )
                    expansion = "apoc_or_store_expand" if expand_depth > 1 else "store_expand"
                except Exception:
                    graph_edges = [
                        edge
                        for edge in self.store.list_edges(scope)
                        if edge.source_id == seed_id or edge.target_id == seed_id
                    ][:DEFAULT_EXPAND_EDGE_LIMIT]
                    expansion = "one_hop_fallback"
            else:
                graph_edges = [
                    edge
                    for edge in self.store.list_edges(scope)
                    if edge.source_id == seed_id or edge.target_id == seed_id
                ][:DEFAULT_EXPAND_EDGE_LIMIT]
                expansion = "one_hop"
            hit["graph_neighbors"] = [
                {
                    "id": edge.id,
                    "rel_type": edge.rel_type,
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                }
                for edge in graph_edges
            ]
            hit["graph_expansion"] = expansion
            # Light hybrid boost: structural connectivity hints denser local context.
            neighbor_count = len(hit["graph_neighbors"])
            if neighbor_count:
                hit["score"] = round(min(1.0, float(hit["score"]) + 0.01 * min(neighbor_count, 5)), 6)
