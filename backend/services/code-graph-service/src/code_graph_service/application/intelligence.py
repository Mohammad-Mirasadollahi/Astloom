"""Wave 1–3 intelligence use cases: explore, risk, architecture, hybrid search, freshness."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..domain.architecture import (
    ArchNode,
    approximate_betweenness,
    degree_hubs,
    knowledge_gaps,
    shortest_path,
    suggested_questions,
    surprising_connections,
)
from ..domain.communities import detect_communities, last_community_algorithm
from ..domain.enums import RelType, SymbolKind
from ..domain.errors import NotFoundError, ValidationError
from ..domain.explore import ExploreSymbol, build_explore_pack, extract_query_terms
from ..domain.external_calls import is_blast_call_edge
from ..domain.flows import FlowNode, detect_entry_points, trace_flow
from ..domain.freshness import FreshnessState
from ..domain.hybrid_search import lexical_rank, searchable_text
from ..domain.models import Scope
from ..domain.parsing_authority import DURABLE_EDGE_REFERENCE_KIND
from ..domain.ports import list_symbols_compact
from ..domain.risk import RiskFactors, compute_risk_score, risk_level
from ..domain.test_links import is_test_path
from .support import GraphServiceSupport


class IntelligenceUseCases(GraphServiceSupport):
    freshness: FreshnessState

    def _ensure_freshness(self) -> FreshnessState:
        state = getattr(self, "freshness", None)
        if state is None:
            self.freshness = FreshnessState()
        return self.freshness

    def mark_file_pending(self, file_path: str) -> dict[str, Any]:
        state = self._ensure_freshness()
        state.mark_pending(file_path)
        return state.stale_banner([file_path])

    def mark_files_pending(self, file_paths: list[str]) -> dict[str, Any]:
        """Batch mark many paths pending (agent coding bursts must not N× sync)."""
        state = self._ensure_freshness()
        cleaned = [p for p in (file_paths or []) if str(p).strip()]
        if not cleaned:
            raise ValidationError("file_paths is required")
        state.mark_pending_many(cleaned)
        return state.stale_banner(cleaned)

    def reconcile_after_edit(
        self,
        file_paths: list[str],
        *,
        scope: Scope | None = None,
        root_path: str | None = None,
        actor_id: str = "agent",
        correlation_id: str = "",
        idempotency_key: str = "",
        run_sync: bool = False,
    ) -> dict[str, Any]:
        """ADR 48 one-way converge: edit session → mark pending → optional AST re-ingest.

        Does not write CODE_REL from LSP. Graph updates happen only when ``run_sync``
        triggers ``sync_repo`` / pending ingest (structural reference_kind).
        """
        banner = self.mark_files_pending(file_paths)
        payload: dict[str, Any] = {
            "reference_kind": DURABLE_EDGE_REFERENCE_KIND,
            "mode": "pending_only",
            "reconciled": False,
            "freshness": banner,
            "note": (
                "Durable knowledge↔code edges update only via AST re-ingest; "
                "LSP/IDE session tools must not dual-write CODE_REL (ADR 48)."
            ),
        }
        if not run_sync:
            return payload
        if scope is None:
            raise ValidationError("scope is required when run_sync=true")
        root = str(root_path or "").strip()
        if not root:
            raise ValidationError("root_path is required when run_sync=true")
        sync_fn = getattr(self, "sync_repo", None)
        if not callable(sync_fn):
            raise ValidationError("sync_repo is not available on this service")
        corr = str(correlation_id or "").strip() or "reconcile-after-edit"
        idem = str(idempotency_key or "").strip() or f"reconcile:{corr}"
        sync_result = sync_fn(
            scope,
            actor_id,
            corr,
            idem,
            {"root_path": root},
        )
        payload["mode"] = getattr(sync_result, "mode", "incremental")
        payload["reconciled"] = True
        to_dict = getattr(sync_result, "to_dict", None)
        payload["sync"] = to_dict() if callable(to_dict) else {"mode": payload["mode"]}
        payload["freshness"] = (
            self.freshness_status(scope) if hasattr(self, "freshness_status") else banner
        )
        return payload

    def clear_pending_sync(self, file_path: str | None = None) -> dict[str, Any]:
        state = self._ensure_freshness()
        state.clear_pending(file_path)
        return state.stale_banner()

    def freshness_status(self, scope: Scope | None = None) -> dict[str, Any]:
        banner = self._ensure_freshness().stale_banner()
        if scope is not None:
            durable = self._durable_last_sync_at(scope)
            if durable:
                banner["last_sync_at"] = durable
        return banner

    def record_sync_stamp(self, scope: Scope) -> str:
        """Persist last_sync_at in the store so CLI status survives process restarts."""
        from ..domain.enums import DocStatus, SymbolKind
        from ..domain.hashing import digest, now_iso
        from ..domain.models import GraphSymbol

        stamp = now_iso()
        sid = f"meta:last_sync:{scope.project_id}"
        previous = self._maybe_get(sid, scope) if hasattr(self, "_maybe_get") else None
        if previous is None:
            try:
                previous = self.store.get_symbol(sid, scope)
            except Exception:  # noqa: BLE001
                previous = None
        self.store.put_symbol(
            GraphSymbol(
                id=sid,
                scope=scope,
                kind=SymbolKind.DOCUMENTATION,
                file_path="__astloom__/last_sync",
                name="last_sync",
                qualified_name="__astloom__.last_sync",
                signature="last_sync",
                body=stamp,
                hash_value=digest(stamp),
                ai_documentation="",
                doc_status=DocStatus.UNCHANGED,
                embedding=[],
                version=(previous.version + 1) if previous else 1,
                created_at=previous.created_at if previous else stamp,
                updated_at=stamp,
                language="",
            )
        )
        state = self._ensure_freshness()
        state.last_sync_at = __import__("time").time()
        state.verified = True
        return stamp

    def _durable_last_sync_at(self, scope: Scope) -> str | None:
        sid = f"meta:last_sync:{scope.project_id}"
        try:
            meta = self.store.get_symbol(sid, scope)
        except Exception:  # noqa: BLE001
            return None
        return str(meta.updated_at or meta.body or "") or None

    def _community_map(self, scope: Scope) -> dict[str, int]:
        symbols = [
            s
            for s in list_symbols_compact(self.store, scope)
            if s.kind in {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS}
        ]
        edges = [
            (e.source_id, e.target_id, e.rel_type)
            for e in self.store.list_edges(scope)
            if e.rel_type not in {RelType.CALLS.value, "CALLS"}
            or is_blast_call_edge(
                target_id=e.target_id,
                metadata=e.metadata,
                confidence=e.confidence,
            )
        ]
        labels = {s.id: s.name for s in symbols}
        communities = detect_communities([s.id for s in symbols], edges, labels_by_id=labels)
        return {mid: c.id for c in communities for mid in c.member_ids}

    def community_of_symbol(
        self,
        scope: Scope,
        symbol_id: str,
        *,
        member_limit: int = 30,
    ) -> dict[str, Any]:
        """Return Leiden/Louvain community membership for one seed symbol."""
        from ..domain.impact import escalate_hint

        symbol = self.store.get_symbol(symbol_id, scope)
        member_limit = max(1, min(int(member_limit), 200))
        symbols = [
            s
            for s in list_symbols_compact(self.store, scope)
            if s.kind in {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS, SymbolKind.ROUTE}
        ]
        by_id = {s.id: s for s in symbols}
        edges = [
            (e.source_id, e.target_id, e.rel_type)
            for e in self.store.list_edges(scope)
            if e.rel_type not in {RelType.CALLS.value, "CALLS"}
            or is_blast_call_edge(
                target_id=e.target_id,
                metadata=e.metadata,
                confidence=e.confidence,
            )
        ]
        labels = {s.id: s.name for s in symbols}
        communities = detect_communities([s.id for s in symbols], edges, labels_by_id=labels)
        community_map = {mid: c for c in communities for mid in c.member_ids}
        community = community_map.get(symbol.id)
        if community is None:
            # Seed may be file/import — try any symbol id in full map
            all_ids = [s.id for s in list_symbols_compact(self.store, scope)]
            all_edges = [
                (e.source_id, e.target_id, e.rel_type)
                for e in self.store.list_edges(scope)
                if e.rel_type not in {RelType.CALLS.value, "CALLS"}
                or is_blast_call_edge(
                    target_id=e.target_id,
                    metadata=e.metadata,
                    confidence=e.confidence,
                )
            ]
            all_labels = {s.id: s.name for s in list_symbols_compact(self.store, scope)}
            communities = detect_communities(all_ids, all_edges, labels_by_id=all_labels)
            community_map = {mid: c for c in communities for mid in c.member_ids}
            community = community_map.get(symbol.id)
            by_id = {s.id: s for s in list_symbols_compact(self.store, scope)}
        if community is None:
            payload = {
                "symbol": self._symbol_view(symbol),
                "community_id": None,
                "label": None,
                "size": 0,
                "members": [],
                "algorithm": last_community_algorithm(),
                "escalate_hint": escalate_hint(sparse=True),
            }
        else:
            members = []
            for mid in community.member_ids:
                sym = by_id.get(mid)
                if sym is None:
                    continue
                members.append(
                    {
                        "symbol_id": mid,
                        "qualified_name": sym.qualified_name,
                        "kind": sym.kind.value,
                        "file_path": sym.file_path,
                    }
                )
                if len(members) >= member_limit:
                    break
            payload = {
                "symbol": self._symbol_view(symbol),
                "community_id": community.id,
                "label": community.label,
                "size": community.size,
                "members": members,
                "returned": len(members),
                "algorithm": last_community_algorithm(),
                "escalate_hint": escalate_hint(sparse=False),
            }
        freshness_fn = getattr(self, "freshness_status", None)
        if callable(freshness_fn):
            payload["freshness"] = freshness_fn(scope)
        return payload

    def explore(
        self,
        scope: Scope,
        query: str,
        *,
        top_k: int = 12,
        max_depth: int = 2,
        budget_chars: int | None = None,
    ) -> dict[str, Any]:
        if not query.strip():
            raise ValidationError("query is required")
        top_k = max(1, min(int(top_k), 40))
        max_depth = max(1, min(int(max_depth), 4))

        hybrid = self.hybrid_search(scope, query, top_k=max(5, top_k // 2))
        terms = extract_query_terms(query)
        scored: dict[str, float] = {}
        for hit in hybrid.get("hits") or []:
            sid = str(hit.get("symbol_id") or "")
            if sid:
                scored[sid] = max(scored.get(sid, 0.0), float(hit.get("score") or 0.5) + 1.0)
        seed_ids = sorted(scored, key=lambda i: scored[i], reverse=True)[: max(3, top_k // 2)]

        structural_rels = {
            RelType.CALLS.value,
            "CALLS",
            RelType.HTTP_CALLS.value,
            RelType.ASYNC_CALLS.value,
            "HTTP_CALLS",
            "ASYNC_CALLS",
        }
        calls_out: dict[str, list[str]] = defaultdict(list)
        calls_in: dict[str, list[str]] = defaultdict(list)
        neighborhood: list[Any] = []
        edge_fetch = getattr(self, "_structural_edges_for_seed", None)
        for sid in seed_ids:
            if callable(edge_fetch):
                neighborhood.extend(
                    edge_fetch(
                        scope,
                        sid,
                        max_depth=max_depth,
                        direction="both",
                        rel_types=["CALLS", "HTTP_CALLS", "ASYNC_CALLS"],
                    )
                )
            else:
                for edge in self.store.list_edges(scope):
                    if edge.source_id == sid or edge.target_id == sid:
                        neighborhood.append(edge)
        seen_edge: set[str] = set()
        for edge in neighborhood:
            eid = getattr(edge, "id", None) or f"{edge.source_id}:{edge.rel_type}:{edge.target_id}"
            if eid in seen_edge:
                continue
            seen_edge.add(str(eid))
            if edge.rel_type not in structural_rels:
                continue
            if edge.rel_type in {RelType.CALLS.value, "CALLS"} and not is_blast_call_edge(
                target_id=edge.target_id,
                metadata=edge.metadata,
                confidence=edge.confidence,
            ):
                continue
            calls_out[edge.source_id].append(edge.target_id)
            calls_in[edge.target_id].append(edge.source_id)

        candidate_ids = set(seed_ids)
        for sid in list(seed_ids):
            for nbr in calls_out.get(sid, []) + calls_in.get(sid, []):
                candidate_ids.add(nbr)
            for edge in neighborhood:
                candidate_ids.add(edge.source_id)
                candidate_ids.add(edge.target_id)

        by_id = {}
        for sid in candidate_ids:
            sym = self._maybe_get(sid, scope)
            if sym is not None:
                by_id[sid] = sym

        call_path: list[str] = []
        for sid in seed_ids:
            if sid not in by_id:
                continue
            flow_nodes = {
                i: FlowNode(
                    id=s.id,
                    name=s.name,
                    qualified_name=s.qualified_name,
                    file_path=s.file_path,
                    signature=s.signature,
                    body=s.body,
                )
                for i, s in by_id.items()
            }
            flow = trace_flow(
                flow_nodes[sid],
                flow_nodes,
                dict(calls_out),
                max_depth=max_depth,
                max_nodes=top_k * 2,
            )
            for nid in flow.path_ids:
                if nid not in call_path:
                    call_path.append(nid)

        candidate_ids |= set(call_path)

        explore_syms: list[ExploreSymbol] = []
        for sid in candidate_ids:
            sym = by_id.get(sid) or self._maybe_get(sid, scope)
            if sym is None or sym.kind in {
                SymbolKind.FILE,
                SymbolKind.UNRESOLVED,
                SymbolKind.EXTERNAL,
                SymbolKind.IMPORT,
            }:
                continue
            if not (sym.body or "").strip():
                full = self._maybe_get(sid, scope)
                if full is not None:
                    sym = full
            explore_syms.append(
                ExploreSymbol(
                    id=sym.id,
                    name=sym.name,
                    qualified_name=sym.qualified_name,
                    file_path=sym.file_path,
                    signature=sym.signature or sym.name,
                    body=sym.body or "",
                    kind=sym.kind.value,
                    score=scored.get(sid, 0.1),
                )
            )
            if len(explore_syms) >= top_k * 2:
                break

        pack = build_explore_pack(
            query,
            explore_syms,
            call_path_ids=call_path,
            file_count=len({s.file_path for s in explore_syms if s.file_path}),
            budget_chars=budget_chars,
        )
        paths = [sec.file_path for sec in pack.sections]
        try:
            from repo_pack import tokens_from_chars

            estimated_tokens = tokens_from_chars(pack.used_chars)
        except ImportError:
            estimated_tokens = (pack.used_chars + 3) // 4
        return {
            "query": pack.query,
            "budget_chars": pack.budget_chars,
            "used_chars": pack.used_chars,
            "estimated_tokens": estimated_tokens,
            "token_estimate_method": "chars_div_4",
            "seed_ids": seed_ids,
            "call_path_ids": pack.call_path_ids,
            "terms": terms,
            "notes": pack.notes,
            "sections": [
                {
                    "file_path": sec.file_path,
                    "skeletonized": sec.skeletonized,
                    "symbols": sec.symbols,
                }
                for sec in pack.sections
            ],
            "edge_confidence_policy": (
                "exact|probable|ambiguous|unresolved|external on CALLS; "
                "ROUTES_TO/TESTED_BY/HTTP_CALLS/dynamic_dispatch are heuristic"
            ),
            "freshness": self._ensure_freshness().stale_banner(paths),
            "retrieval": hybrid.get("mode"),
            "escalate_hint": {
                "next_tools": [
                    "astloom_code_graph_callers",
                    "astloom_code_graph_impact",
                    "astloom_code_graph_call_path",
                    "astloom_code_graph_hybrid_search",
                ],
                "prefer_before_raw_read": True,
                "reason": (
                    "structural_sparse"
                    if not pack.sections
                    else "semantic_question"
                ),
            },
        }

    def call_path_pack(
        self,
        scope: Scope,
        symbol_id: str,
        *,
        max_depth: int = 4,
        max_nodes: int = 40,
    ) -> dict[str, Any]:
        """Compact outbound call-path pack from a seed (Codebase-Memory hybrid)."""
        from ..domain.impact import escalate_hint

        symbol = self.store.get_symbol(symbol_id, scope)
        max_depth = max(1, min(int(max_depth), 8))
        max_nodes = max(2, min(int(max_nodes), 200))
        symbols = {
            s.id: s
            for s in list_symbols_compact(self.store, scope)
            if s.kind
            in {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS, SymbolKind.ROUTE}
        }
        calls_out: dict[str, list[str]] = defaultdict(list)
        structural_rels = {
            RelType.CALLS.value,
            RelType.HTTP_CALLS.value,
            RelType.ASYNC_CALLS.value,
        }
        for edge in self.store.list_edges(scope):
            if edge.rel_type not in structural_rels:
                continue
            if edge.rel_type == RelType.CALLS.value and not is_blast_call_edge(
                target_id=edge.target_id,
                metadata=edge.metadata,
                confidence=edge.confidence,
            ):
                continue
            calls_out[edge.source_id].append(edge.target_id)
        flow_nodes = {
            i: FlowNode(
                id=s.id,
                name=s.name,
                qualified_name=s.qualified_name,
                file_path=s.file_path,
                signature=s.signature,
                body=s.body,
            )
            for i, s in symbols.items()
        }
        if symbol.id not in flow_nodes:
            flow_nodes[symbol.id] = FlowNode(
                id=symbol.id,
                name=symbol.name,
                qualified_name=symbol.qualified_name,
                file_path=symbol.file_path,
                signature=symbol.signature,
                body=symbol.body,
            )
        flow = trace_flow(
            flow_nodes[symbol.id],
            flow_nodes,
            dict(calls_out),
            max_depth=max_depth,
            max_nodes=max_nodes,
        )
        path_rows = []
        for nid in flow.path_ids:
            sym = symbols.get(nid) or self._maybe_get(nid, scope)
            if sym is None:
                continue
            path_rows.append(
                {
                    "symbol_id": nid,
                    "qualified_name": sym.qualified_name,
                    "kind": sym.kind.value,
                    "file_path": sym.file_path,
                    "signature": sym.signature,
                }
            )
        sparse = len(path_rows) <= 1
        payload = {
            "symbol": self._symbol_view(symbol),
            "call_path_ids": flow.path_ids,
            "path": path_rows,
            "depth": flow.depth,
            "max_depth": max_depth,
            "escalate_hint": escalate_hint(
                reason="ok" if not sparse else "structural_sparse",
                sparse=sparse,
            ),
        }
        freshness_fn = getattr(self, "freshness_status", None)
        if callable(freshness_fn):
            payload["freshness"] = freshness_fn(scope)
        return payload

    def hybrid_search(self, scope: Scope, query: str, *, top_k: int = 10) -> dict[str, Any]:
        if not query.strip():
            raise ValidationError("query is required")
        top_k = max(1, min(int(top_k), 50))
        fulltext = getattr(self.store, "fulltext_search", None)
        fts_ids: list[str] = []
        fts_method = None
        if callable(fulltext):
            try:
                rows = fulltext(scope, query, top_k=top_k * 2)
                fts_ids = [str(r["symbol_id"]) for r in rows if r.get("symbol_id")]
                if rows:
                    fts_method = str(rows[0].get("method") or "store.fulltext")
            except Exception:
                fts_ids = []

        lexical_ids: list[str] = []
        symbols: list[Any] = []
        if not fts_ids:
            name_search = getattr(self.store, "symbol_name_search", None)
            if callable(name_search):
                try:
                    rows = name_search(scope, query, top_k=top_k * 2)
                    lexical_ids = [str(r["symbol_id"]) for r in rows if r.get("symbol_id")]
                except Exception:
                    lexical_ids = []
            if not lexical_ids:
                symbols = [
                    s
                    for s in list_symbols_compact(self.store, scope)
                    if s.kind
                    in {
                        SymbolKind.FUNCTION,
                        SymbolKind.METHOD,
                        SymbolKind.CLASS,
                        SymbolKind.DOCUMENTATION,
                        SymbolKind.RATIONALE,
                        SymbolKind.ROUTE,
                    }
                ]
                corpus = [
                    (
                        s.id,
                        searchable_text(
                            name=s.name,
                            qualified_name=s.qualified_name,
                            signature=s.signature or "",
                            file_path=s.file_path or "",
                            ai_documentation=s.ai_documentation or "",
                            body=s.body or "",
                        ),
                    )
                    for s in symbols
                ]
                lexical_ids = lexical_rank(query, corpus, top_k=top_k * 2)

        semantic_ids: list[str] = []
        embedding_backend = "unknown"
        semantic_error: str | None = None
        embedder = getattr(self, "embeddings", None)
        if embedder is not None:
            embedding_backend = getattr(embedder, "backend_name", None) or getattr(
                embedder, "model", "stub"
            )
        try:
            from ..pg_thread_local import is_transient_db_error
        except Exception:  # noqa: BLE001
            is_transient_db_error = lambda _exc: False  # type: ignore[assignment,misc]

        def _collect_semantic() -> list[str]:
            ids: list[str] = []
            for hit in self.semantic_search(scope, query, top_k=top_k * 2):  # type: ignore[attr-defined]
                sym = hit.get("symbol") if isinstance(hit.get("symbol"), dict) else {}
                sid = str(sym.get("id") or "")
                if sid:
                    ids.append(sid)
            return ids

        if not fts_ids:
            try:
                semantic_ids = _collect_semantic()
            except Exception as exc:  # noqa: BLE001 — lexical/FTS must still return
                if is_transient_db_error(exc):
                    reset = getattr(self, "reset_database_connections", None)
                    if callable(reset):
                        try:
                            reset()
                        except Exception:  # noqa: BLE001
                            pass
                    try:
                        semantic_ids = _collect_semantic()
                    except Exception as retry_exc:  # noqa: BLE001
                        semantic_ids = []
                        semantic_error = f"{type(retry_exc).__name__}:{retry_exc}"[:300]
                    else:
                        semantic_error = None
                else:
                    semantic_ids = []
                    semantic_error = f"{type(exc).__name__}:{exc}"[:300]

        from ..domain.hybrid_search import coalesce_rank_lists, rrf_merge

        lists = coalesce_rank_lists(lexical_ids, semantic_ids, fts_ids) or [lexical_ids]
        merged = rrf_merge(*lists)
        by_id = {s.id: s for s in symbols}
        hits = []
        for sid, score in merged[:top_k]:
            sym = by_id.get(sid)
            if sym is None:
                try:
                    sym = self.store.get_symbol(sid, scope)
                except NotFoundError:
                    continue
            hits.append(
                {
                    "symbol_id": sid,
                    "score": round(score, 6),
                    "qualified_name": sym.qualified_name,
                    "kind": sym.kind.value,
                    "file_path": sym.file_path,
                }
            )
        if fts_ids and semantic_ids:
            mode = "hybrid_rrf_fts_semantic_bm25"
        elif semantic_ids:
            mode = "hybrid_rrf_semantic_bm25"
        else:
            mode = "bm25"
        payload = {
            "query": query,
            "mode": mode,
            "hits": hits,
            "channels": {
                "bm25": len(lexical_ids),
                "semantic": len(semantic_ids),
                "fts": len(fts_ids),
            },
            "embedding_backend": embedding_backend,
            "fts_method": fts_method,
        }
        if semantic_error:
            payload["semantic_error"] = semantic_error
        elif (
            not semantic_ids
            and getattr(self, "embedding_index", None) is None
            and embedder is not None
        ):
            # Empty semantic with a live embedder usually means in-store vectors
            # are absent because pgvector was never wired (MCP DATABASE_URL gap).
            payload["semantic_error"] = (
                "embedding_index_unavailable: semantic channel empty without pgvector"
            )
        return payload

    def architecture_overview(self, scope: Scope, *, top_n: int = 10) -> dict[str, Any]:
        symbols = list(list_symbols_compact(self.store, scope))
        edges = [
            edge
            for edge in self.store.list_edges(scope)
            if edge.rel_type not in {RelType.CALLS.value, "CALLS"}
            or is_blast_call_edge(
                target_id=edge.target_id,
                metadata=edge.metadata,
                confidence=edge.confidence,
            )
        ]
        useful = [
            s
            for s in symbols
            if s.kind in {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS}
        ]
        edge_triples = [(e.source_id, e.target_id, e.rel_type) for e in edges]
        labels = {s.id: s.name for s in useful}
        communities = detect_communities([s.id for s in useful], edge_triples, labels_by_id=labels)
        community_map = {mid: c.id for c in communities for mid in c.member_ids}
        arch_nodes = [
            ArchNode(
                id=s.id,
                name=s.name,
                qualified_name=s.qualified_name,
                file_path=s.file_path,
                kind=s.kind.value,
                community_id=community_map.get(s.id),
            )
            for s in useful
        ]
        undirected = [(e.source_id, e.target_id) for e in edges]
        by_id = {s.id: s for s in symbols}
        tested = {
            e.source_id for e in edges if e.rel_type in {RelType.TESTED_BY.value, "TESTED_BY"}
        }
        for e in edges:
            if e.rel_type not in {RelType.CALLS.value, "CALLS"}:
                continue
            src = by_id.get(e.source_id)
            if src is not None and is_test_path(src.file_path or ""):
                tested.add(e.target_id)
        hubs = degree_hubs(arch_nodes, edge_triples, top_n=top_n)
        bridges = approximate_betweenness(arch_nodes, undirected, top_n=top_n)
        gaps = knowledge_gaps(arch_nodes, edge_triples, tested_targets=tested)
        surprise_edges = [
            (e.source_id, e.target_id, e.rel_type, e.confidence.value) for e in edges
        ]
        surprises = surprising_connections(arch_nodes, surprise_edges, top_n=top_n)
        return {
            "communities": [
                {
                    "id": c.id,
                    "label": c.label,
                    "size": c.size,
                    "members": list(c.member_ids)[:40],
                }
                for c in communities[:40]
            ],
            "hubs": hubs,
            "bridges": bridges,
            "knowledge_gaps": gaps,
            "surprising_connections": surprises,
            "suggested_questions": suggested_questions(hubs, bridges, surprises),
            "algorithm": last_community_algorithm(),
        }

    def symbol_path(
        self,
        scope: Scope,
        start_id: str,
        end_id: str,
        *,
        max_depth: int = 12,
    ) -> dict[str, Any]:
        if not start_id.strip() or not end_id.strip():
            raise ValidationError("start_id and end_id are required")

        def resolve(token: str) -> str:
            if self._maybe_get(token, scope) is not None:
                return token
            for s in list_symbols_compact(self.store, scope):
                if s.qualified_name == token or s.name == token:
                    return s.id
            raise ValidationError(f"symbol not found: {token}")

        start = resolve(start_id)
        end = resolve(end_id)
        path: list[str] = []
        method = "in_memory_bfs"
        store_path = getattr(self.store, "shortest_path_ids", None)
        if callable(store_path):
            try:
                path = store_path(scope, start, end, max_depth=max_depth) or []
                if path:
                    method = "neo4j_shortest_path"
            except Exception:
                path = []
        if not path:
            undirected = [(e.source_id, e.target_id) for e in self.store.list_edges(scope)]
            path = shortest_path(start, end, undirected, max_depth=max_depth)
            method = "in_memory_bfs"
        views = []
        for sid in path:
            try:
                views.append(self._symbol_view(self.store.get_symbol(sid, scope)))
            except NotFoundError:
                views.append({"id": sid})
        return {
            "start_id": start,
            "end_id": end,
            "hops": max(0, len(path) - 1),
            "path_ids": path,
            "symbols": views,
            "reachable": bool(path),
            "method": method,
        }

    def detect_changes(
        self,
        scope: Scope,
        changed_files: list[str],
        *,
        include_flows: bool = True,
    ) -> dict[str, Any]:
        if not changed_files:
            raise ValidationError("changed_files is required")
        changed_norm = {f.replace("\\", "/") for f in changed_files}
        symbols = list(list_symbols_compact(self.store, scope))
        edges = list(self.store.list_edges(scope))
        community_map = self._community_map(scope)

        calls_out: dict[str, list[str]] = defaultdict(list)
        callers_of: dict[str, list[str]] = defaultdict(list)
        tested_by: dict[str, list[str]] = defaultdict(list)
        route_handlers: set[str] = set()
        for edge in edges:
            if edge.rel_type in {RelType.CALLS.value, "CALLS"} and is_blast_call_edge(
                target_id=edge.target_id,
                metadata=edge.metadata,
                confidence=edge.confidence,
            ):
                calls_out[edge.source_id].append(edge.target_id)
                callers_of[edge.target_id].append(edge.source_id)
            elif edge.rel_type in {RelType.TESTED_BY.value, "TESTED_BY"}:
                tested_by[edge.source_id].append(edge.target_id)
            elif edge.rel_type in {RelType.ROUTES_TO.value, "ROUTES_TO"}:
                route_handlers.add(edge.target_id)

        changed_syms = [
            s
            for s in symbols
            if s.file_path.replace("\\", "/") in changed_norm
            and s.kind in {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS}
        ]

        flow_nodes = {
            s.id: FlowNode(
                id=s.id,
                name=s.name,
                qualified_name=s.qualified_name,
                file_path=s.file_path,
                signature=s.signature,
                body=s.body,
            )
            for s in symbols
            if s.kind in {SymbolKind.FUNCTION, SymbolKind.METHOD}
        }
        call_pairs = [
            (e.source_id, e.target_id)
            for e in edges
            if e.rel_type in {RelType.CALLS.value, "CALLS"}
            and is_blast_call_edge(
                target_id=e.target_id,
                metadata=e.metadata,
                confidence=e.confidence,
            )
        ]
        entries = detect_entry_points(
            flow_nodes.values(), call_pairs, route_handler_ids=route_handlers
        )
        flows = []
        if include_flows:
            for entry in entries[:40]:
                flows.append(trace_flow(entry, flow_nodes, dict(calls_out)))

        membership: dict[str, list[float]] = defaultdict(list)
        for flow in flows:
            for nid in flow.path_ids:
                membership[nid].append(flow.criticality)

        node_risks: list[dict[str, Any]] = []
        test_gaps: list[dict[str, Any]] = []
        for sym in changed_syms:
            tests = tested_by.get(sym.id, [])
            cross = 0
            my_c = community_map.get(sym.id)
            if my_c is not None:
                for caller in callers_of.get(sym.id, []):
                    cc = community_map.get(caller)
                    if cc is not None and cc != my_c:
                        cross += 1
            factors = RiskFactors(
                flow_criticalities=tuple(membership.get(sym.id, ())),
                flow_membership_count=len(membership.get(sym.id, [])),
                cross_community_callers=cross,
                test_count=len(tests),
                caller_count=len(callers_of.get(sym.id, [])),
                name=sym.name,
                qualified_name=sym.qualified_name,
            )
            score = compute_risk_score(factors)
            node_risks.append(
                {
                    "symbol_id": sym.id,
                    "qualified_name": sym.qualified_name,
                    "file_path": sym.file_path,
                    "risk_score": score,
                    "risk_level": risk_level(score),
                    "caller_count": factors.caller_count,
                    "test_count": factors.test_count,
                    "flow_count": factors.flow_membership_count,
                    "cross_community_callers": cross,
                    "community_id": my_c,
                }
            )
            if not tests and not is_test_path(sym.file_path):
                test_gaps.append(
                    {
                        "symbol_id": sym.id,
                        "qualified_name": sym.qualified_name,
                        "file_path": sym.file_path,
                    }
                )

        node_risks.sort(key=lambda r: r["risk_score"], reverse=True)
        overall = max((r["risk_score"] for r in node_risks), default=0.0)
        changed_ids = {s.id for s in changed_syms}
        affected_flows = [
            {
                "entry": f.entry_name,
                "depth": f.depth,
                "file_count": f.file_count,
                "criticality": f.criticality,
                "path_ids": f.path_ids[:20],
            }
            for f in flows
            if any(nid in changed_ids for nid in f.path_ids)
        ]
        affected_flows.sort(key=lambda f: f["criticality"], reverse=True)
        return {
            "changed_files": sorted(changed_norm),
            "risk_score": overall,
            "risk_level": risk_level(overall),
            "changed_functions": node_risks[:50],
            "review_priorities": node_risks[:10],
            "test_gaps": test_gaps[:30],
            "affected_flows": affected_flows[:20],
            "summary": (
                f"{len(changed_syms)} changed symbols across {len(changed_norm)} files; "
                f"overall risk {overall:.2f} ({risk_level(overall)}); "
                f"{len(test_gaps)} untested hotspots"
            ),
            "freshness": self._ensure_freshness().stale_banner(sorted(changed_norm)),
        }
