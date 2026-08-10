"""Compatibility shim — implementation lives in ``code_graph_service.neo4j``."""

from __future__ import annotations

from .neo4j import Neo4jStore, _lucene_query, lucene_query

__all__ = ["Neo4jStore", "_lucene_query", "lucene_query"]
