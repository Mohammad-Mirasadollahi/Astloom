"""Runtime-observed CALL edges and static reconciliation (GAP-T02).

Role: Parse runtime trace payloads into observed CALLS and reconcile them with
static edges (boost matches, demote contradictions, emit new observed edges).
Source of truth: durable CODE_REL after reconcile; ``provenance=runtime_trace``
marks observed edges. Allowed: boost/demote confidence; emit CALLS for resolved
endpoints. Forbidden: inventing code symbols beyond unresolved placeholders;
LSP/IDE writer tags on durable edges (ADR 48).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from .confidence_policy import clamp_confidence, confidence_rank, demote_confidence
from .enums import CallConfidence, RelType
from .errors import ValidationError
from .models import GraphEdge

ResolveFn = Callable[[str], str | None]

PROVENANCE_RUNTIME_TRACE = "runtime_trace"
CALL_REL_TYPES = frozenset(
    {
        RelType.CALLS.value,
        RelType.HTTP_CALLS.value,
        RelType.ASYNC_CALLS.value,
    }
)


@dataclass(frozen=True)
class ObservedCall:
    """One runtime-observed caller → callee edge."""

    source: str
    target: str
    call_site: str = ""
    count: int = 1
    file_path: str = "runtime"
    rel_type: str = RelType.CALLS.value
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReconcileAction:
    """Mutation to apply against the store after reconciliation."""

    kind: str  # emit | boost | demote
    source_id: str
    target_id: str
    confidence: CallConfidence
    metadata: dict[str, Any]
    edge_id: str | None = None
    rel_type: str = RelType.CALLS.value
    file_path: str = "runtime"
    link_key: str | None = None


def parse_runtime_trace_payload(payload: Mapping[str, Any] | list[Any] | None) -> list[ObservedCall]:
    """Parse HTTP/service payload into observed calls.

    Accepted shapes:
    - ``{"calls": [ {...}, ... ]}``
    - bare list of call objects
    Each call object needs ``source`` / ``caller`` and ``target`` / ``callee``
    (symbol id or qualified_name). Optional: ``call_site``, ``count``, ``file_path``,
    ``rel_type``, ``metadata``.
    """
    if payload is None:
        raise ValidationError("runtime trace payload is required")
    if isinstance(payload, list):
        raw_calls = payload
    elif isinstance(payload, Mapping):
        raw_calls = payload.get("calls")
        if raw_calls is None:
            raise ValidationError("runtime trace payload requires 'calls'")
        if not isinstance(raw_calls, list):
            raise ValidationError("'calls' must be a list")
    else:
        raise ValidationError("runtime trace payload must be an object or list")

    out: list[ObservedCall] = []
    for idx, item in enumerate(raw_calls):
        if not isinstance(item, Mapping):
            raise ValidationError(f"calls[{idx}] must be an object")
        source = str(item.get("source") or item.get("caller") or "").strip()
        target = str(item.get("target") or item.get("callee") or "").strip()
        if not source or not target:
            raise ValidationError(f"calls[{idx}] requires source/caller and target/callee")
        count_raw = item.get("count", 1)
        try:
            count = max(1, int(count_raw))
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"calls[{idx}].count must be an integer") from exc
        rel = str(item.get("rel_type") or RelType.CALLS.value).strip().upper() or RelType.CALLS.value
        meta = item.get("metadata")
        if meta is None:
            meta_dict: dict[str, Any] = {}
        elif isinstance(meta, Mapping):
            meta_dict = dict(meta)
        else:
            raise ValidationError(f"calls[{idx}].metadata must be an object")
        out.append(
            ObservedCall(
                source=source,
                target=target,
                call_site=str(item.get("call_site") or "").strip(),
                count=count,
                file_path=str(item.get("file_path") or "runtime").strip() or "runtime",
                rel_type=rel,
                metadata=meta_dict,
            )
        )
    return out


def _edge_pair_key(source_id: str, target_id: str) -> tuple[str, str]:
    return (source_id, target_id)


def _caller_site_key(source_id: str, call_site: str, call_name: str) -> str:
    site = (call_site or "").strip()
    if site:
        return f"{source_id}|site:{site}"
    name = (call_name or "").strip()
    if name:
        return f"{source_id}|call:{name}"
    return source_id


def reconcile_runtime_traces(
    *,
    observed: Iterable[ObservedCall],
    static_edges: Iterable[GraphEdge],
    resolve_symbol: ResolveFn,
) -> list[ReconcileAction]:
    """Reconcile observed runtime CALLS with existing static edges.

    - Matching static CALLS → boost confidence + ``runtime_confirmed``.
    - Observed pairs with no static edge → emit ``provenance=runtime_trace``.
    - Static CALLS from the same call site / caller contradicted by a different
      observed target → demote confidence + ``runtime_contradicted``.
    """
    static_calls = [
        e
        for e in static_edges
        if str(e.rel_type or "").upper() in CALL_REL_TYPES
    ]
    by_pair: dict[tuple[str, str], GraphEdge] = {}
    by_caller_site: dict[str, list[GraphEdge]] = {}
    for edge in static_calls:
        by_pair[_edge_pair_key(edge.source_id, edge.target_id)] = edge
        call_name = str((edge.metadata or {}).get("call") or "")
        site = str((edge.metadata or {}).get("call_site") or "")
        key = _caller_site_key(edge.source_id, site, call_name)
        by_caller_site.setdefault(key, []).append(edge)

    actions: list[ReconcileAction] = []
    seen_emit: set[tuple[str, str]] = set()
    observed_targets_by_site: dict[str, set[str]] = {}

    for obs in observed:
        source_id = resolve_symbol(obs.source)
        target_id = resolve_symbol(obs.target)
        if not source_id or not target_id:
            # Skip unresolved endpoints rather than inventing durable symbols here;
            # application layer may materialize placeholders before calling us.
            continue
        pair = _edge_pair_key(source_id, target_id)
        site_key = _caller_site_key(source_id, obs.call_site, obs.target)
        observed_targets_by_site.setdefault(site_key, set()).add(target_id)

        meta_base = {
            "provenance": PROVENANCE_RUNTIME_TRACE,
            "runtime_count": obs.count,
            "call_site": obs.call_site,
            **obs.metadata,
        }

        existing = by_pair.get(pair)
        if existing is not None:
            current = (
                existing.confidence
                if isinstance(existing.confidence, CallConfidence)
                else CallConfidence(str(existing.confidence))
            )
            boosted = clamp_confidence(current, via="runtime_trace")
            merged = dict(existing.metadata or {})
            merged.update(meta_base)
            merged["runtime_confirmed"] = True
            actions.append(
                ReconcileAction(
                    kind="boost",
                    source_id=source_id,
                    target_id=target_id,
                    confidence=boosted,
                    metadata=merged,
                    edge_id=existing.id,
                    rel_type=str(existing.rel_type),
                    file_path=str((existing.metadata or {}).get("file_path") or obs.file_path),
                    link_key=f"runtime-boost:{existing.id}",
                )
            )
            continue

        if pair in seen_emit:
            continue
        seen_emit.add(pair)
        conf = clamp_confidence(CallConfidence.PROBABLE, via="runtime_trace")
        actions.append(
            ReconcileAction(
                kind="emit",
                source_id=source_id,
                target_id=target_id,
                confidence=conf,
                metadata={**meta_base, "origin": "runtime_trace"},
                rel_type=obs.rel_type.upper(),
                file_path=obs.file_path,
                link_key=f"runtime:{source_id}:{target_id}:{obs.call_site or 'obs'}",
            )
        )

    # Demote static edges contradicted at the same call site / caller.
    demoted_ids: set[str] = set()
    for site_key, targets in observed_targets_by_site.items():
        for edge in by_caller_site.get(site_key, ()):
            if edge.target_id in targets:
                continue
            if edge.id in demoted_ids:
                continue
            demoted_ids.add(edge.id)
            conf = (
                edge.confidence
                if isinstance(edge.confidence, CallConfidence)
                else CallConfidence(str(edge.confidence))
            )
            demoted = demote_confidence(conf)
            if confidence_rank(demoted) >= confidence_rank(CallConfidence.PROBABLE):
                demoted = CallConfidence.AMBIGUOUS
            merged = dict(edge.metadata or {})
            merged["runtime_contradicted"] = True
            merged["provenance_static"] = merged.get("provenance") or "static"
            actions.append(
                ReconcileAction(
                    kind="demote",
                    source_id=edge.source_id,
                    target_id=edge.target_id,
                    confidence=demoted,
                    metadata=merged,
                    edge_id=edge.id,
                    rel_type=str(edge.rel_type),
                    file_path=str((edge.metadata or {}).get("file_path") or "runtime"),
                    link_key=f"runtime-demote:{edge.id}",
                )
            )

    return actions
