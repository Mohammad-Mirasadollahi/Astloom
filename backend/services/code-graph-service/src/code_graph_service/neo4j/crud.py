"""Neo4j Store CRUD: symbols, edges, idempotency, outbox, wipe.

Role: hydrate and persist CodeSymbol / CODE_REL for the Neo4j SoR adapter.
Source of truth: Neo4j node/rel properties; required enums are kind and doc_status.
Allowed: coalesce edge confidence; purge or skip symbols with null required enums.
Forbidden: invent SymbolKind/DocStatus; abort a full list_* on one corrupt row.
"""

from __future__ import annotations

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
    ValidationError,
)
from ..domain.confidence_policy import parse_call_confidence
from . import cypher


class Neo4jCrudMixin:
    """Persistence port methods for CodeSymbol / CODE_REL."""

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id, scope.project_group_id or ""))

    @staticmethod
    def _parse_symbol_kind(raw: Any, *, symbol_id: str) -> SymbolKind:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raise ValidationError(f"CodeSymbol {symbol_id!r} has null/blank kind")
        try:
            return SymbolKind(raw)
        except ValueError as exc:
            raise ValidationError(f"CodeSymbol {symbol_id!r} has invalid kind {raw!r}") from exc

    @staticmethod
    def _parse_doc_status(raw: Any, *, symbol_id: str) -> DocStatus:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raise ValidationError(f"CodeSymbol {symbol_id!r} has null/blank doc_status")
        try:
            return DocStatus(raw)
        except ValueError as exc:
            raise ValidationError(f"CodeSymbol {symbol_id!r} has invalid doc_status {raw!r}") from exc

    def _symbol_from_node(self, node: Any, scope: Scope) -> GraphSymbol:
        symbol_id = str(node.get("id") or "")
        embedding = node.get("embedding") or []
        if isinstance(embedding, str):
            embedding = json.loads(embedding)
        metadata_raw = node.get("metadata_json") or node.get("metadata") or {}
        if isinstance(metadata_raw, str):
            metadata = json.loads(metadata_raw or "{}")
        else:
            metadata = dict(metadata_raw or {})
        return GraphSymbol(
            id=node["id"],
            scope=scope,
            kind=self._parse_symbol_kind(node.get("kind"), symbol_id=symbol_id or "?"),
            file_path=node["file_path"],
            name=node["name"],
            qualified_name=node["qualified_name"],
            signature=node["signature"],
            body=node["body"],
            hash_value=node["hash_value"],
            ai_documentation=node["ai_documentation"],
            doc_status=self._parse_doc_status(node.get("doc_status"), symbol_id=symbol_id or "?"),
            embedding=list(embedding),
            visibility=node["visibility"],
            version=int(node.get("version") or 1),
            created_at=str(node["created_at"]),
            updated_at=str(node["updated_at"]),
            language=str(node.get("language") or ""),
            hash_version=str(node.get("hash_version") or ""),
            parser_version=str(node.get("parser_version") or ""),
            metadata=metadata,
        )

    def _symbols_from_rows(self, rows: list[Any], scope: Scope) -> list[GraphSymbol]:
        """Hydrate list results; skip rows with corrupt required enums (defense in depth)."""
        out: list[GraphSymbol] = []
        for row in rows:
            try:
                out.append(self._symbol_from_node(row["n"], scope))
            except ValidationError:
                continue
        return out

    def get_symbol(self, symbol_id: str, scope: Scope) -> GraphSymbol:
        with self._driver.session(database=self._database) as session:
            record = session.run(
                cypher.GET_SYMBOL,
                id=symbol_id,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
            ).single()
        if record is None:
            raise NotFoundError("symbol not found in project scope")
        return self._symbol_from_node(record["n"], scope)

    def put_symbol(self, symbol: GraphSymbol) -> None:
        scope = symbol.scope
        with self._driver.session(database=self._database) as session:
            session.run(
                cypher.PUT_SYMBOL,
                id=symbol.id,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
                project_group_id=scope.project_group_id,
                kind=symbol.kind.value,
                file_path=symbol.file_path,
                name=symbol.name,
                qualified_name=symbol.qualified_name,
                signature=symbol.signature,
                body=symbol.body,
                hash_value=symbol.hash_value,
                ai_documentation=symbol.ai_documentation,
                doc_status=symbol.doc_status.value,
                embedding=list(symbol.embedding),
                visibility=symbol.visibility,
                version=symbol.version,
                created_at=symbol.created_at,
                updated_at=symbol.updated_at,
                language=symbol.language or "",
                hash_version=symbol.hash_version or "",
                parser_version=symbol.parser_version or "",
                metadata_json=json.dumps(dict(symbol.metadata or {}), sort_keys=True),
            )

    def delete_symbol(self, symbol_id: str, scope: Scope) -> None:
        with self._driver.session(database=self._database) as session:
            session.run(
                cypher.DELETE_SYMBOL,
                id=symbol_id,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
            )

    def delete_symbols(self, symbol_ids: list[str], scope: Scope) -> None:
        ids = [str(symbol_id) for symbol_id in symbol_ids if str(symbol_id)]
        if not ids:
            return
        with self._driver.session(database=self._database) as session:
            session.run(
                cypher.DELETE_SYMBOLS,
                symbol_ids=ids,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
            )

    def list_symbols(self, scope: Scope) -> list[GraphSymbol]:
        with self._driver.session(database=self._database) as session:
            rows = list(
                session.run(
                    cypher.LIST_SYMBOLS,
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                )
            )
        return self._symbols_from_rows(rows, scope)

    def list_symbols_lean(self, scope: Scope) -> list[GraphSymbol]:
        """Symbols without living-doc blobs (for dead-code / reachability scans)."""
        with self._driver.session(database=self._database) as session:
            rows = list(
                session.run(
                    cypher.LIST_SYMBOLS_LEAN,
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                )
            )
        return self._symbols_from_rows(rows, scope)

    def list_symbols_for_file(self, scope: Scope, file_path: str) -> list[GraphSymbol]:
        path = str(file_path or "").replace("\\", "/")
        with self._driver.session(database=self._database) as session:
            rows = list(
                session.run(
                    cypher.LIST_SYMBOLS_FOR_FILE,
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                    file_path=path,
                )
            )
        return self._symbols_from_rows(rows, scope)

    def get_symbol_by_qualified_name(self, scope: Scope, qualified_name: str) -> GraphSymbol | None:
        with self._driver.session(database=self._database) as session:
            record = session.run(
                cypher.GET_SYMBOL_BY_QUALIFIED_NAME,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
                qualified_name=qualified_name,
            ).single()
        if record is None:
            return None
        return self._symbol_from_node(record["n"], scope)

    def delete_file_edges(self, scope: Scope, file_path: str) -> None:
        with self._driver.session(database=self._database) as session:
            session.run(
                cypher.DELETE_FILE_EDGES,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
                file_path=file_path,
            )

    def delete_edge(self, scope: Scope, edge_id: str) -> None:
        with self._driver.session(database=self._database) as session:
            session.run(
                cypher.DELETE_EDGE,
                id=edge_id,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
            )

    def put_edge(self, edge: GraphEdge) -> None:
        scope = edge.scope
        metadata = dict(edge.metadata or {})
        file_path = str(metadata.get("file_path") or "")
        with self._driver.session(database=self._database) as session:
            session.run(
                cypher.PUT_EDGE,
                id=edge.id,
                source_id=edge.source_id,
                target_id=edge.target_id,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
                project_group_id=scope.project_group_id,
                rel_type=edge.rel_type,
                confidence=parse_call_confidence(edge.confidence).value,
                file_path=file_path,
                metadata_json=json.dumps(metadata, sort_keys=True),
            )

    def put_edges(self, edges: list[GraphEdge]) -> None:
        if not edges:
            return
        rows: list[dict[str, Any]] = []
        for edge in edges:
            scope = edge.scope
            metadata = dict(edge.metadata or {})
            rows.append(
                {
                    "id": edge.id,
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "tenant_id": scope.tenant_id,
                    "workspace_id": scope.workspace_id,
                    "project_id": scope.project_id,
                    "project_group_id": scope.project_group_id,
                    "rel_type": edge.rel_type,
                    "confidence": parse_call_confidence(edge.confidence).value,
                    "file_path": str(metadata.get("file_path") or ""),
                    "metadata_json": json.dumps(metadata, sort_keys=True),
                }
            )
        with self._driver.session(database=self._database) as session:
            session.run(cypher.PUT_EDGES, edges=rows)

    def list_edges(
        self,
        scope: Scope,
        *,
        rel_type: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> list[GraphEdge]:
        with self._driver.session(database=self._database) as session:
            rows = list(
                session.run(
                    cypher.LIST_EDGES,
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                    rel_type=rel_type,
                    source_id=source_id,
                    target_id=target_id,
                )
            )
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

    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None:
        with self._driver.session(database=self._database) as session:
            record = session.run(
                cypher.BEGIN_IDEMPOTENCY,
                scope_key=self._scope_key(scope),
                idempotency_key=key,
                resource_type=resource,
            ).single()
        return None if record is None else record["resource_id"]

    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None:
        with self._driver.session(database=self._database) as session:
            record = session.run(
                cypher.COMPLETE_IDEMPOTENCY,
                scope_key=self._scope_key(scope),
                idempotency_key=key,
                resource_type=resource,
                resource_id=resource_id,
            ).single()
        if record is None or record["resource_id"] != resource_id:
            raise ConflictError("idempotency key already bound to another resource")

    def append_event(self, event: dict[str, Any]) -> None:
        with self._driver.session(database=self._database) as session:
            session.run(
                cypher.APPEND_EVENT,
                event_id=event["event_id"],
                event_type=event["event_type"],
                payload_json=json.dumps(event, sort_keys=True),
            )

    def outbox(self) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            rows = list(session.run(cypher.OUTBOX))
        return [json.loads(row["payload_json"]) for row in rows]

    def wipe_scope(self, scope: Scope) -> dict[str, int]:
        with self._driver.session(database=self._database) as session:
            symbols = session.run(
                cypher.WIPE_SYMBOLS,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
            ).single()
            edges = session.run(
                cypher.WIPE_EDGES,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
            ).single()
            idem = session.run(
                cypher.WIPE_IDEMPOTENCY,
                scope_key=self._scope_key(scope),
            ).single()
        self._capabilities_cache = None
        return {
            "symbols": int((symbols or {}).get("deleted") or 0),
            "edges": int((edges or {}).get("deleted") or 0),
            "idempotency": int((idem or {}).get("deleted") or 0),
        }
