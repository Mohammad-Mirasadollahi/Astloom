"""Ingest runtime-observed CALL edges (GAP-T02).

Role: Application entry for runtime CALL payloads → durable CODE_REL reconcile.
Source of truth: store edges after boost/demote/emit; idempotency key
``runtime_traces``. Allowed: skip unresolved endpoints; soft-count unresolved
tokens. Forbidden: inventing symbol identities; LSP writer tags on durable edges.
"""

from __future__ import annotations

from typing import Any

from ...domain.enums import RelType
from ...domain.errors import NotFoundError, ValidationError
from ...domain.hashing import digest
from ...domain.models import GraphEdge, Scope
from ...domain.runtime_traces import (
    PROVENANCE_RUNTIME_TRACE,
    parse_runtime_trace_payload,
    reconcile_runtime_traces,
)
from ...domain.symbol_resolve import resolve_linked_symbol


class RuntimeTraceIngestMixin:
    """Application surface for runtime-trace CALL ingest + static reconcile."""

    def ingest_runtime_traces(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any] | list[Any],
    ) -> dict[str, Any]:
        """Parse runtime CALL observations, reconcile with static edges, persist.

        Idempotent on ``idempotency_key`` for resource ``runtime_traces``.
        """
        existing = self.store.begin_idempotency(scope, idempotency_key, "runtime_traces")
        if existing is not None:
            return {
                "idempotent_replay": True,
                "resource_id": existing,
                "observed": 0,
                "emitted": 0,
                "boosted": 0,
                "demoted": 0,
                "unresolved": 0,
            }

        observed = parse_runtime_trace_payload(payload)
        if not observed:
            raise ValidationError("runtime trace payload has no calls")

        unresolved: list[str] = []

        def resolve(token: str) -> str | None:
            hit = resolve_linked_symbol(self.store, scope, token)
            if hit is not None:
                return hit.id
            # Accept already-known unresolved / any symbol id.
            try:
                return self.store.get_symbol(token, scope).id
            except NotFoundError:
                unresolved.append(token)
                return None

        actions = reconcile_runtime_traces(
            observed=observed,
            static_edges=self.store.list_edges(scope),
            resolve_symbol=resolve,
        )

        emitted = boosted = demoted = 0
        for action in actions:
            if action.kind == "emit":
                emitted += self._put_edge(
                    scope,
                    action.rel_type or RelType.CALLS.value,
                    action.source_id,
                    action.target_id,
                    file_path=action.file_path,
                    confidence=action.confidence,
                    metadata=action.metadata,
                    link_key=action.link_key,
                )
            elif action.kind in {"boost", "demote"} and action.edge_id:
                try:
                    prior = next(
                        e for e in self.store.list_edges(scope) if e.id == action.edge_id
                    )
                except StopIteration:
                    continue
                updated = GraphEdge(
                    id=prior.id,
                    scope=prior.scope,
                    rel_type=prior.rel_type,
                    source_id=prior.source_id,
                    target_id=prior.target_id,
                    confidence=action.confidence,
                    metadata=action.metadata,
                )
                self.store.put_edge(updated)
                if action.kind == "boost":
                    boosted += 1
                else:
                    demoted += 1

        resource_id = f"runtime_traces:{digest(idempotency_key)[:16]}"
        self.store.complete_idempotency(scope, idempotency_key, "runtime_traces", resource_id)
        self.store.append_event(
            self._event(
                "code_graph.runtime_traces.ingested",
                scope,
                actor_id,
                correlation_id,
                idempotency_key,
                {
                    "observed": len(observed),
                    "emitted": emitted,
                    "boosted": boosted,
                    "demoted": demoted,
                    "unresolved_tokens": sorted(set(unresolved)),
                    "provenance": PROVENANCE_RUNTIME_TRACE,
                },
            )
        )
        return {
            "idempotent_replay": False,
            "resource_id": resource_id,
            "observed": len(observed),
            "emitted": emitted,
            "boosted": boosted,
            "demoted": demoted,
            "unresolved": len(set(unresolved)),
            "unresolved_tokens": sorted(set(unresolved)),
        }
