"""
Role: Enforce ADR 48 parsing authority — durable CODE_REL comes only from AST ingest.
Source of truth / invariants: metadata.provenance / writer / source_of_truth must never
mark language-server or IDE-session writers on durable edges; LSP may inform an edit
session only. Allowed failure: ValidationError before Store.put_edge. Forbidden failure:
silently accepting LSP dual-write into Neo4j/Postgres graph SoR.
"""

from __future__ import annotations

from typing import Any, Mapping

from .errors import ValidationError

# Session / IDE writers that must not become a second durable graph SoR (ADR 48 §Decision 1.3).
FORBIDDEN_DURABLE_EDGE_WRITERS: frozenset[str] = frozenset(
    {
        "lsp",
        "language_server",
        "session_lsp",
        "jetbrains",
        "jetbrains_plugin",
        "ide_rename",
        "ide_reference",
        "serena",
    }
)

DURABLE_EDGE_REFERENCE_KIND = "structural"
SESSION_EDGE_REFERENCE_KIND = "ide_semantic"


def _norm_tag(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def durable_edge_writer_tags(metadata: Mapping[str, Any] | None) -> set[str]:
    """Collect writer-like tags from edge metadata (provenance / writer / source_of_truth)."""
    if not metadata:
        return set()
    tags: set[str] = set()
    for key in ("provenance", "writer", "source_of_truth", "edge_writer"):
        tag = _norm_tag(metadata.get(key))
        if tag:
            tags.add(tag)
    if metadata.get("lsp") is True or _norm_tag(metadata.get("lsp")) in {"1", "true", "yes"}:
        tags.add("lsp")
    return tags


def assert_durable_edge_metadata_allowed(metadata: Mapping[str, Any] | None) -> None:
    """Reject LSP / IDE-session writers on durable CODE_REL (ADR 48)."""
    bad = durable_edge_writer_tags(metadata) & FORBIDDEN_DURABLE_EDGE_WRITERS
    if not bad:
        return
    writers = ", ".join(sorted(bad))
    raise ValidationError(
        "durable CODE_REL must not be written from LSP/IDE session "
        f"(forbidden writer tag(s): {writers}); re-ingest via AST instead (ADR 48)"
    )
