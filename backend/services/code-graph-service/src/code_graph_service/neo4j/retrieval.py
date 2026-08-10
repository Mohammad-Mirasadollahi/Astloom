"""Neo4j retrieval helpers: fulltext, path, neighborhood, degree ranking."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..core import (
    ConflictError,
    DocStatus,
    GraphEdge,
    GraphSymbol,
    NotFoundError,
    Scope,
    SymbolKind,
)
from ..domain.confidence_policy import parse_call_confidence
from .constants import REL as _REL
from .lucene import lucene_query as _lucene_query

class Neo4jRetrievalMixin:
    """Graph retrieval features beyond basic Store CRUD."""

    def fulltext_search(
        self,
        scope: Scope,
        query: str,
        *,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Neo4j Lucene fulltext search (BM25-like); empty when unavailable."""
        top_k = max(1, min(int(top_k), 100))
        q = (query or "").strip()
        if not q or not self.capabilities().get("fulltext"):
            return []
        lucene_q = _lucene_query(q)
        if not lucene_q:
            return []
        index_name = self._fulltext_index_name()
        with self._driver.session(database=self._database) as session:
            try:
                rows = list(
                    session.run(
                        """
                        CALL db.index.fulltext.queryNodes($index_name, $q)
                        YIELD node, score
                        WHERE node.tenant_id = $tenant_id
                          AND node.workspace_id = $workspace_id
                          AND node.project_id = $project_id
                        RETURN node.id AS symbol_id, score
                        ORDER BY score DESC
                        LIMIT $top_k
                        """,
                        index_name=index_name,
                        q=lucene_q,
                        tenant_id=scope.tenant_id,
                        workspace_id=scope.workspace_id,
                        project_id=scope.project_id,
                        top_k=top_k,
                    )
                )
            except Exception:
                return []
        return [
            {"symbol_id": row["symbol_id"], "score": float(row["score"]), "method": "neo4j.fulltext"}
            for row in rows
        ]

    def _fulltext_index_name(self) -> str:
        with self._driver.session(database=self._database) as session:
            try:
                record = session.run(
                    "SHOW FULLTEXT INDEXES YIELD name "
                    "WHERE name = 'code_symbol_fulltext_v2' RETURN name LIMIT 1"
                ).single()
                if record:
                    return "code_symbol_fulltext_v2"
            except Exception:
                pass
        return "code_symbol_fulltext"

    def shortest_path_ids(
        self,
        scope: Scope,
        start_id: str,
        end_id: str,
        *,
        max_depth: int = 12,
    ) -> list[str]:
        """Shortest undirected CODE_REL path via Cypher shortestPath; else []."""
        max_depth = max(1, min(int(max_depth), 20))
        # Cypher shortestPath is core Neo4j (no APOC required).
        depth = max(1, min(int(max_depth), 12))
        with self._driver.session(database=self._database) as session:
            try:
                record = session.run(
                    f"""
                    MATCH (a:CodeSymbol {{id: $start_id}}), (b:CodeSymbol {{id: $end_id}})
                    WHERE a.tenant_id = $tenant_id AND b.tenant_id = $tenant_id
                      AND a.workspace_id = $workspace_id AND b.workspace_id = $workspace_id
                      AND a.project_id = $project_id AND b.project_id = $project_id
                    MATCH path = shortestPath((a)-[:CODE_REL*..{depth}]-(b))
                    RETURN [n IN nodes(path) | n.id] AS ids
                    """,
                    start_id=start_id,
                    end_id=end_id,
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                ).single()
            except Exception:
                return []
        if not record or not record.get("ids"):
            return []
        return [str(x) for x in record["ids"]]
    def expand_neighborhood(
        self,
        scope: Scope,
        symbol_id: str,
        *,
        max_depth: int = 2,
        rel_type: str | None = None,
        limit: int = 100,
    ) -> list[GraphEdge]:
        """Multi-hop neighborhood via APOC when available; otherwise one-hop listing."""
        max_depth = max(1, min(int(max_depth), 5))
        limit = max(1, min(int(limit), 500))
        caps = self.capabilities()
        if not caps.get("apoc"):
            edges = [
                edge
                for edge in self.list_edges(scope)
                if edge.source_id == symbol_id or edge.target_id == symbol_id
            ]
            if rel_type:
                edges = [edge for edge in edges if edge.rel_type == rel_type.upper()]
            return edges[:limit]

        rel_filter = ""
        params: dict[str, Any] = {
            "id": symbol_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "max_depth": max_depth,
            "limit": limit,
        }
        if rel_type:
            rel_filter = "AND r.rel_type = $rel_type"
            params["rel_type"] = rel_type.upper()

        query = f"""
        MATCH (start:CodeSymbol {{id: $id}})
        WHERE start.tenant_id = $tenant_id
          AND start.workspace_id = $workspace_id
          AND start.project_id = $project_id
        CALL apoc.path.expandConfig(start, {{
          relationshipFilter: 'CODE_REL',
          minLevel: 1,
          maxLevel: $max_depth,
          uniqueness: 'RELATIONSHIP_GLOBAL',
          limit: $limit
        }})
        YIELD path
        WITH relationships(path) AS rels
        UNWIND rels AS r
        WITH DISTINCT r
        WHERE r.tenant_id = $tenant_id
          AND r.workspace_id = $workspace_id
          AND r.project_id = $project_id
          {rel_filter}
        MATCH (source:CodeSymbol)-[r]->(target:CodeSymbol)
        RETURN r.id AS id,
               r.rel_type AS rel_type,
               r.confidence AS confidence,
               r.metadata_json AS metadata_json,
               source.id AS source_id,
               target.id AS target_id
        LIMIT $limit
        """
        with self._driver.session(database=self._database) as session:
            rows = list(session.run(query, **params))
        return [
            GraphEdge(
                id=row["id"],
                scope=scope,
                rel_type=row["rel_type"],
                source_id=row["source_id"],
                target_id=row["target_id"],
                confidence=parse_call_confidence(row["confidence"]),
                metadata=json.loads(row["metadata_json"] or "{}"),
            )
            for row in rows
        ]

    def rank_symbols_by_degree(
        self,
        scope: Scope,
        *,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Degree-based importance ranking.

        Prefers ``gds.degree`` when the GDS *Community* plugin is loaded (no
        Enterprise license key required). Always falls back to Cypher degree.
        See docs/07-code-knowledge-graph/32-intentional-fallbacks-and-neo4j-plugin-licensing.md.
        """
        top_k = max(1, min(int(top_k), 100))
        caps = self.capabilities()
        # Native Cypher projection (gds.graph.project aggregation) — not deprecated
        # gds.graph.project.cypher. Graph name must be unique per scope for concurrency.
        graph_name = "cgr_" + hashlib.sha256(self._scope_key(scope).encode()).hexdigest()[:16]
        with self._driver.session(database=self._database) as session:
            if caps.get("gds"):
                try:
                    session.run(
                        "CALL gds.graph.drop($graph_name, false) YIELD graphName RETURN graphName",
                        graph_name=graph_name,
                    )
                    session.run(
                        """
                        MATCH (source:CodeSymbol)
                        WHERE source.tenant_id = $tenant_id
                          AND source.workspace_id = $workspace_id
                          AND source.project_id = $project_id
                          AND source.kind <> 'documentation'
                          AND source.kind <> 'unresolved'
                          AND source.kind <> 'external'
                        OPTIONAL MATCH (source)-[:CODE_REL]->(target:CodeSymbol)
                        WHERE target IS NULL OR (
                          target.tenant_id = $tenant_id
                          AND target.workspace_id = $workspace_id
                          AND target.project_id = $project_id
                        )
                        WITH gds.graph.project($graph_name, source, target) AS g
                        RETURN g.graphName AS graphName
                        """,
                        graph_name=graph_name,
                        tenant_id=scope.tenant_id,
                        workspace_id=scope.workspace_id,
                        project_id=scope.project_id,
                    )
                    rows = list(
                        session.run(
                            """
                            CALL gds.degree.stream($graph_name, {concurrency: $concurrency})
                            YIELD nodeId, score
                            WITH gds.util.asNode(nodeId) AS n, score
                            RETURN n.id AS id, n.qualified_name AS qualified_name, n.kind AS kind, score
                            ORDER BY score DESC, qualified_name
                            LIMIT $top_k
                            """,
                            graph_name=graph_name,
                            concurrency=self._gds_concurrency,
                            top_k=top_k,
                        )
                    )
                    session.run(
                        "CALL gds.graph.drop($graph_name, false) YIELD graphName RETURN graphName",
                        graph_name=graph_name,
                    )
                    return [
                        {
                            "symbol_id": row["id"],
                            "qualified_name": row["qualified_name"],
                            "kind": row["kind"],
                            "score": float(row["score"]),
                            "method": "gds.degree",
                        }
                        for row in rows
                    ]
                except Exception:
                    try:
                        session.run(
                            "CALL gds.graph.drop($graph_name, false) YIELD graphName RETURN graphName",
                            graph_name=graph_name,
                        )
                    except Exception:
                        pass

            rows = list(
                session.run(
                    f"""
                    MATCH (n:CodeSymbol)
                    WHERE n.tenant_id = $tenant_id
                      AND n.workspace_id = $workspace_id
                      AND n.project_id = $project_id
                      AND n.kind <> 'documentation'
                      AND n.kind <> 'unresolved'
                      AND n.kind <> 'external'
                    OPTIONAL MATCH (n)-[r:{_REL}]-(m:CodeSymbol)
                    WHERE m.tenant_id = $tenant_id
                      AND m.workspace_id = $workspace_id
                      AND m.project_id = $project_id
                    RETURN n.id AS id,
                           n.qualified_name AS qualified_name,
                           n.kind AS kind,
                           count(r) AS score
                    ORDER BY score DESC, qualified_name
                    LIMIT $top_k
                    """,
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                    top_k=top_k,
                )
            )
        return [
            {
                "symbol_id": row["id"],
                "qualified_name": row["qualified_name"],
                "kind": row["kind"],
                "score": float(row["score"]),
                "method": "cypher.degree",
            }
            for row in rows
        ]

    def neighborhood_edges(
        self,
        scope: Scope,
        seed_id: str,
        *,
        max_depth: int = 3,
        direction: str = "both",
        rel_types: list[str] | None = None,
        limit: int = 2000,
    ) -> list[GraphEdge]:
        """Directed multi-hop CODE_REL edges around a seed (Cypher; scale path for callers/impact)."""
        depth = max(1, min(int(max_depth), 8))
        limit = max(1, min(int(limit), 5000))
        direction_n = (direction or "both").strip().lower()
        if direction_n not in {"upstream", "downstream", "both"}:
            direction_n = "both"
        rels = [r.upper() for r in (rel_types or ["CALLS", "HTTP_CALLS", "ASYNC_CALLS", "ROUTES_TO"])]
        patterns: list[str] = []
        if direction_n in {"upstream", "both"}:
            patterns.append(
                f"(seed)<-[r:{_REL}*1..{depth}]-(other:CodeSymbol)"
            )
        if direction_n in {"downstream", "both"}:
            patterns.append(
                f"(seed)-[r:{_REL}*1..{depth}]->(other:CodeSymbol)"
            )
        edges: list[GraphEdge] = []
        seen: set[str] = set()
        with self._driver.session(database=self._database) as session:
            for pattern in patterns:
                cypher = f"""
                    MATCH (seed:CodeSymbol {{id: $seed_id}})
                    WHERE seed.tenant_id = $tenant_id
                      AND seed.workspace_id = $workspace_id
                      AND seed.project_id = $project_id
                    MATCH p = {pattern}
                    WHERE other.tenant_id = $tenant_id
                      AND other.workspace_id = $workspace_id
                      AND other.project_id = $project_id
                      AND all(rel IN relationships(p) WHERE rel.rel_type IN $rels)
                    UNWIND relationships(p) AS edge
                    WITH DISTINCT edge
                    MATCH (a:CodeSymbol)-[edge]->(b:CodeSymbol)
                    RETURN edge.id AS id,
                           edge.rel_type AS rel_type,
                           a.id AS source_id,
                           b.id AS target_id,
                           edge.confidence AS confidence,
                           edge.metadata_json AS metadata_json
                    LIMIT $limit
                    """
                try:
                    rows = list(
                        session.run(
                            cypher,
                            seed_id=seed_id,
                            tenant_id=scope.tenant_id,
                            workspace_id=scope.workspace_id,
                            project_id=scope.project_id,
                            rels=rels,
                            limit=limit,
                        )
                    )
                except Exception:
                    continue
                for row in rows:
                    eid = str(row["id"] or "")
                    if eid and eid in seen:
                        continue
                    if eid:
                        seen.add(eid)
                    conf = parse_call_confidence(row["confidence"])
                    edges.append(
                        GraphEdge(
                            id=eid or f"cypher:{row['source_id']}:{row['target_id']}",
                            scope=scope,
                            rel_type=str(row["rel_type"] or "CALLS"),
                            source_id=str(row["source_id"]),
                            target_id=str(row["target_id"]),
                            confidence=conf,
                            metadata=json.loads(row["metadata_json"] or "{}"),
                        )
                    )
        return edges
