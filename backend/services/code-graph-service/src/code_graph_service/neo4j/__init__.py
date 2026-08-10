"""Modular Neo4j store package."""

from .lucene import lucene_query
from .store import Neo4jStore

# Backward-compatible private alias used by tests.
_lucene_query = lucene_query

__all__ = ["Neo4jStore", "lucene_query", "_lucene_query"]
