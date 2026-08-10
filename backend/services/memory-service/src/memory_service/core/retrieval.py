"""Context retrieval and explainability commands."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .constants import HISTORY_TERMS
from .enums import MemoryKind, MemoryState
from .errors import ValidationError
from .helpers import estimate_tokens, now, tokenize
from .models import ContextBundle, MemoryItem, Scope


class RetrievalCommands:
    def retrieve_context(self, scope: Scope, actor: str, correlation_id: str, query: str, token_budget: int | None = None) -> ContextBundle:
        if not query.strip():
            raise ValidationError("query is required")
        budget = token_budget or self.profile.context_token_budget
        if budget <= 0:
            raise ValidationError("token_budget must be positive")
        terms = tokenize(query)
        wants_history = bool(terms & HISTORY_TERMS)
        candidates = self._refresh_expired_working(scope, self.store.list_memory(scope))
        embedding_hits = self._embedding_hits(scope, query, candidates)
        embedding_boosts = {
            mid: float(hit["score"]) * self.profile.semantic_weight for mid, hit in embedding_hits.items()
        }
        dense_stage = "off"
        if embedding_hits:
            stages = {str(hit.get("retrieval") or "") for hit in embedding_hits.values()}
            if any("turbovec" in stage for stage in stages):
                dense_stage = "pgvector+turbovec"
            else:
                dense_stage = "pgvector"
        selected: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        used_tokens = 0
        scored = sorted(
            (
                (self._score(item, terms, wants_history) + embedding_boosts.get(item.id, 0.0), item)
                for item in candidates
            ),
            key=lambda pair: (-pair[0], pair[1].created_at, pair[1].id),
        )
        for score, item in scored:
            reason = self._exclude_reason(item, score, wants_history)
            if reason:
                excluded.append({"id": item.id, "reason": reason, "score": round(score, 3)})
                continue
            token_estimate = estimate_tokens(item.title + " " + item.body)
            if used_tokens + token_estimate > budget:
                excluded.append({"id": item.id, "reason": "token_budget_overflow", "score": round(score, 3)})
                continue
            used_tokens += token_estimate
            hit = embedding_hits.get(item.id)
            selection_reason = "matched query under scoped weight profile"
            if hit is not None:
                selection_reason = f"{selection_reason}; dense={hit.get('retrieval', 'stage1')}"
            entry: dict[str, Any] = {
                "memory": item.public(),
                "score": round(score, 3),
                "selection_reason": selection_reason,
                "token_estimate": token_estimate,
            }
            if hit is not None:
                entry["dense_retrieval"] = hit.get("retrieval")
            selected.append(entry)
        bundle = ContextBundle(str(uuid4()), scope, query, budget, self.profile, selected, excluded, now())
        # Attach bundle-level attribution for explain/audit consumers.
        bundle_public_extra = {
            "dense_retrieval": {
                "stage": dense_stage,
                "pgvector": dense_stage.startswith("pgvector"),
                "turbovec": "turbovec" in dense_stage,
            }
        }
        self.emit(
            "ContextBundleBuilt",
            {**bundle.public(), **bundle_public_extra},
            scope,
            actor,
            correlation_id,
            "",
            bundle.bundle_id,
            [],
        )
        return bundle

    def explain_retrieval(self, scope: Scope, query: str) -> dict[str, Any]:
        terms = tokenize(query)
        wants_history = bool(terms & HISTORY_TERMS)
        dense: dict[str, Any] = {"enabled": False, "stage1": "none", "stage2": "off"}
        embed_store = getattr(self, "embedding_store", None)
        if embed_store is not None and hasattr(embed_store, "search"):
            dense["enabled"] = True
            dense["stage1"] = "pgvector"
            try:
                from vector_index import AnnAcceleratorConfig, turbovec_importable

                cfg = AnnAcceleratorConfig.from_environment()
                if cfg.enabled and turbovec_importable():
                    dense["stage2"] = "turbovec"
                elif cfg.enabled:
                    dense["stage2"] = "turbovec_unavailable_fallback_pgvector"
                else:
                    dense["stage2"] = "off"
            except Exception:
                dense["stage2"] = "off"
        return {
            "query_terms": sorted(terms),
            "wants_history": wants_history,
            "weight_profile": self.profile.__dict__,
            "prompt_cache": {"profile_id": self.profile.profile_id, "version": self.profile.version},
            "dense_retrieval": dense,
            "read_model_id": "memory.context_bundle",
            "attribution": {
                "pgvector": dense["stage1"] == "pgvector",
                "turbovec": dense["stage2"] == "turbovec",
            },
            "candidates": [
                {
                    "id": item.id,
                    "state": item.state.value,
                    "kind": item.kind.value,
                    "score": round(self._score(item, terms, wants_history), 3),
                }
                for item in self.store.list_memory(scope)
            ],
        }

    def _score(self, item: MemoryItem, terms: set[str], wants_history: bool = False) -> float:
        haystack = tokenize(" ".join([item.title, item.body, *item.tags]))
        overlap = len(terms & haystack)
        kind_weight = {
            MemoryKind.SEMANTIC: self.profile.semantic_weight,
            MemoryKind.EPISODIC: self.profile.episodic_weight,
            MemoryKind.WORKING: self.profile.working_weight,
            MemoryKind.RESTRICTED: 0.0,
            MemoryKind.DEPRECATED: 0.0,
        }[item.kind]
        evidence = self.profile.evidence_weight if item.evidence_refs else 0.0
        score = (overlap * kind_weight) + evidence + (item.confidence * self.profile.recency_weight)
        if item.state == MemoryState.ACTIVE and item.kind in {MemoryKind.SEMANTIC, MemoryKind.WORKING}:
            score += self.profile.current_state_boost
        if item.pinned:
            score += self.profile.current_state_boost
        if item.kind == MemoryKind.EPISODIC and not wants_history:
            score -= self.profile.episodic_penalty
        if item.state == MemoryState.CANDIDATE:
            score -= 0.5
        return score

    def _exclude_reason(self, item: MemoryItem, score: float, wants_history: bool = False) -> str | None:
        if item.kind == MemoryKind.RESTRICTED or item.state == MemoryState.RESTRICTED:
            return "restricted_memory_boundary"
        if item.state in {MemoryState.DEPRECATED, MemoryState.ARCHIVED}:
            return "inactive_memory_state"
        if item.state == MemoryState.STALE:
            return "stale_memory_excluded"
        if item.kind == MemoryKind.WORKING and item.is_expired():
            return "working_memory_expired"
        if item.kind == MemoryKind.EPISODIC and not wants_history:
            return "historical_fact_not_requested"
        if score < self.profile.min_relevance_score:
            return "below_relevance_threshold"
        return None
