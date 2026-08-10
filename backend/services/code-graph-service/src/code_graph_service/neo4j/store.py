"""Neo4jStore composition root."""

from __future__ import annotations

from typing import Any

from .crud import Neo4jCrudMixin
from .retrieval import Neo4jRetrievalMixin
from .schema import Neo4jSchemaMixin


class Neo4jStore(Neo4jSchemaMixin, Neo4jRetrievalMixin, Neo4jCrudMixin):
    """Neo4j adapter for the Code Graph Store port (structural graph + outbox)."""

    def __init__(
        self,
        *,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        driver: Any | None = None,
        ensure_schema: bool = True,
        gds_enabled: bool = True,
        gds_concurrency: int = 4,
    ) -> None:
        owns_driver = driver is None
        if owns_driver:
            if not uri.startswith(("bolt://", "bolt+s://", "neo4j://", "neo4j+s://")):
                raise ValueError("Neo4j URI must use bolt://, bolt+s://, neo4j://, or neo4j+s://")
            try:
                from neo4j import GraphDatabase
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("neo4j package is required for Neo4j persistence") from exc
            driver = GraphDatabase.driver(uri, auth=(user, password))
        self._driver = driver
        self._database = database
        self._gds_enabled = bool(gds_enabled)
        # GDS Community Edition hard-caps at 4 cores — never request more.
        self._gds_concurrency = max(1, min(int(gds_concurrency), 4))
        self._capabilities_cache: dict[str, Any] | None = None
        if ensure_schema:
            try:
                self.ensure_schema()
            except Exception:
                if owns_driver:
                    self.close()
                raise

    def close(self) -> None:
        close = getattr(self._driver, "close", None)
        if callable(close):
            close()
