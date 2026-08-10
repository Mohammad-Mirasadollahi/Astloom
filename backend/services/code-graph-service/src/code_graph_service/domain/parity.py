"""Structural parity comparison between two Code Graph Store backends."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .models import Scope
from .ports import Store


@dataclass(frozen=True)
class ParityReport:
    """Result of comparing two stores for one scope."""

    equal: bool
    left_symbol_count: int
    right_symbol_count: int
    left_edge_count: int
    right_edge_count: int
    missing_symbol_ids_on_right: tuple[str, ...] = ()
    extra_symbol_ids_on_right: tuple[str, ...] = ()
    mismatched_symbols: tuple[str, ...] = ()
    missing_edge_ids_on_right: tuple[str, ...] = ()
    extra_edge_ids_on_right: tuple[str, ...] = ()
    mismatched_edges: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _symbol_row(symbol: Any) -> dict[str, Any]:
    return {
        "id": symbol.id,
        "kind": symbol.kind.value if hasattr(symbol.kind, "value") else str(symbol.kind),
        "file_path": symbol.file_path,
        "name": symbol.name,
        "qualified_name": symbol.qualified_name,
        "signature": symbol.signature,
        "hash_value": symbol.hash_value,
        "visibility": symbol.visibility,
    }


def _edge_row(edge: Any) -> dict[str, Any]:
    return {
        "id": edge.id,
        "rel_type": edge.rel_type,
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "confidence": edge.confidence.value
        if hasattr(edge.confidence, "value")
        else str(edge.confidence),
    }


def structural_snapshot(store: Store, scope: Scope) -> dict[str, Any]:
    """Normalize symbols/edges for backend-agnostic comparison."""
    symbols = {_symbol_row(s)["id"]: _symbol_row(s) for s in store.list_symbols(scope)}
    edges = {_edge_row(e)["id"]: _edge_row(e) for e in store.list_edges(scope)}
    return {"symbols": symbols, "edges": edges}


def compare_stores(left: Store, right: Store, scope: Scope) -> ParityReport:
    """Compare structural graph content of two stores for the same scope."""
    left_snap = structural_snapshot(left, scope)
    right_snap = structural_snapshot(right, scope)

    left_ids = set(left_snap["symbols"])
    right_ids = set(right_snap["symbols"])
    missing_syms = tuple(sorted(left_ids - right_ids))
    extra_syms = tuple(sorted(right_ids - left_ids))
    mismatched_syms = tuple(
        sorted(
            sid
            for sid in left_ids & right_ids
            if left_snap["symbols"][sid] != right_snap["symbols"][sid]
        )
    )

    left_edges = set(left_snap["edges"])
    right_edges = set(right_snap["edges"])
    missing_edges = tuple(sorted(left_edges - right_edges))
    extra_edges = tuple(sorted(right_edges - left_edges))
    mismatched_edges = tuple(
        sorted(
            eid
            for eid in left_edges & right_edges
            if left_snap["edges"][eid] != right_snap["edges"][eid]
        )
    )

    equal = not (
        missing_syms
        or extra_syms
        or mismatched_syms
        or missing_edges
        or extra_edges
        or mismatched_edges
    )
    return ParityReport(
        equal=equal,
        left_symbol_count=len(left_ids),
        right_symbol_count=len(right_ids),
        left_edge_count=len(left_edges),
        right_edge_count=len(right_edges),
        missing_symbol_ids_on_right=missing_syms,
        extra_symbol_ids_on_right=extra_syms,
        mismatched_symbols=mismatched_syms,
        missing_edge_ids_on_right=missing_edges,
        extra_edge_ids_on_right=extra_edges,
        mismatched_edges=mismatched_edges,
    )


def ingest_both_and_compare(
    left_service: Any,
    right_service: Any,
    scope: Scope,
    *,
    agent_id: str,
    correlation_id: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> ParityReport:
    """Ingest the same file into two services and compare store snapshots.

    Uses distinct idempotency key suffixes so each backend records its own key.
    """
    left_service.ingest_file(
        scope,
        agent_id,
        correlation_id,
        f"{idempotency_key}:left",
        payload,
    )
    right_service.ingest_file(
        scope,
        agent_id,
        correlation_id,
        f"{idempotency_key}:right",
        payload,
    )
    return compare_stores(left_service.store, right_service.store, scope)
