"""Neo4j schema bootstrap and capability probes."""

from __future__ import annotations

from typing import Any

from . import cypher


class Neo4jSchemaMixin:
    """Schema constraints/indexes and plugin capability cache."""

    def ensure_schema(self) -> None:
        statements = (
            "CREATE CONSTRAINT code_symbol_id IF NOT EXISTS "
            "FOR (n:CodeSymbol) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT code_outbox_event_id IF NOT EXISTS "
            "FOR (n:CodeOutboxEvent) REQUIRE n.event_id IS UNIQUE",
            "CREATE CONSTRAINT code_idempotency_key IF NOT EXISTS "
            "FOR (n:CodeIdempotency) REQUIRE (n.scope_key, n.idempotency_key, n.resource_type) IS UNIQUE",
            "CREATE INDEX code_symbol_scope IF NOT EXISTS "
            "FOR (n:CodeSymbol) ON (n.tenant_id, n.workspace_id, n.project_id)",
            "CREATE INDEX code_symbol_qualified_name IF NOT EXISTS "
            "FOR (n:CodeSymbol) ON (n.project_id, n.qualified_name)",
            "CREATE INDEX code_symbol_kind IF NOT EXISTS "
            "FOR (n:CodeSymbol) ON (n.kind)",
            # Canonical Lucene fulltext (includes file_path). Legacy
            # `code_symbol_fulltext` without file_path is no longer created;
            # query still falls back if an old DB only has the legacy name.
            "CREATE FULLTEXT INDEX code_symbol_fulltext_v2 IF NOT EXISTS "
            "FOR (n:CodeSymbol) ON EACH "
            "[n.qualified_name, n.name, n.signature, n.file_path, n.ai_documentation]",
        )
        with self._driver.session(database=self._database) as session:
            for statement in statements:
                session.run(statement)
            # Relationship props are not constraint-backed; repair legacy nulls.
            session.run(cypher.BACKFILL_NULL_CONFIDENCE)
            # Symbol kind/doc_status lack Neo4j NOT NULL; purge unusable orphans.
            session.run(cypher.PURGE_NULL_SYMBOL_ENUMS)
        self._capabilities_cache = None

    def capabilities(self) -> dict[str, Any]:
        """Probe APOC / GDS / fulltext (cached until schema refresh).

        ``gds`` is false when ``ASTLOOM_NEO4J_GDS_ENABLED`` is off, even if the
        plugin is installed. Also reports ``gds_enabled`` and ``gds_concurrency``
        (Community Edition hard-capped at 4).
        """
        if self._capabilities_cache is not None:
            return dict(self._capabilities_cache)
        caps: dict[str, Any] = {
            "apoc": False,
            "gds": False,
            "fulltext": False,
            "gds_enabled": self._gds_enabled,
            "gds_concurrency": self._gds_concurrency,
        }
        with self._driver.session(database=self._database) as session:
            try:
                record = session.run("RETURN apoc.version() AS version").single()
                caps["apoc"] = record is not None and bool(record.get("version"))
            except Exception:  # pragma: no cover - depends on runtime plugins
                caps["apoc"] = False
            if self._gds_enabled:
                try:
                    record = session.run("RETURN gds.version() AS version").single()
                    caps["gds"] = record is not None and bool(record.get("version"))
                except Exception:  # pragma: no cover
                    caps["gds"] = False
            else:
                caps["gds"] = False
            try:
                record = session.run(
                    "SHOW FULLTEXT INDEXES YIELD name "
                    "WHERE name IN ['code_symbol_fulltext_v2', 'code_symbol_fulltext'] "
                    "RETURN count(*) AS c"
                ).single()
                caps["fulltext"] = bool(record and int(record["c"]) > 0)
            except Exception:  # pragma: no cover
                caps["fulltext"] = False
        self._capabilities_cache = caps
        return dict(caps)
