"""
Role: Package entry for graph-backed dead-code candidate discovery.
Source of truth: docs/07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md.
Allowed: re-export find_unused_candidates for MCP / QueryUseCases.
Forbidden: mutating the repository; dual SoT in Memory.
"""

from __future__ import annotations

from .find import find_unused_candidates

__all__ = ["find_unused_candidates"]
