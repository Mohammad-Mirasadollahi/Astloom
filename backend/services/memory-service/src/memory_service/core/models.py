"""Memory domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .enums import BatchState, MemoryKind, MemoryState, QuestionState
from .errors import ConflictError, ValidationError
from .helpers import now, parse_timestamp, slug


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    workspace_id: str
    project_id: str
    project_group_id: str | None = None

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.workspace_id.strip(), self.project_id.strip())):
            raise ValidationError("tenant_id, workspace_id, and project_id are required")


@dataclass(frozen=True)
class WeightProfile:
    profile_id: str
    version: int
    semantic_weight: float
    episodic_weight: float
    working_weight: float
    evidence_weight: float
    recency_weight: float
    min_relevance_score: float
    faq_min_observations: int
    faq_min_evidence: int
    context_token_budget: int

    curiosity_min_observations: int = 2
    documentation_draft_min_confidence: float = 0.75
    documentation_task_min_confidence: float = 0.4
    current_state_boost: float = 2.0
    episodic_penalty: float = 1.5

    @classmethod
    def from_catalog(cls, data: dict[str, Any]) -> WeightProfile:
        weights = data.get("feature_weights") or {}
        thresholds = data.get("thresholds") or {}
        return cls(
            profile_id=str(data.get("profile_id") or "default-memory-profile"),
            version=int(data.get("version") or 1),
            semantic_weight=float(weights.get("semantic_weight", 3.0)),
            episodic_weight=float(weights.get("episodic_weight", 1.0)),
            working_weight=float(weights.get("working_weight", 2.0)),
            evidence_weight=float(weights.get("evidence_weight", 1.5)),
            recency_weight=float(weights.get("recency_weight", 0.25)),
            min_relevance_score=float(thresholds.get("min_relevance_score", 2.0)),
            faq_min_observations=int(thresholds.get("faq_min_observations", 2)),
            faq_min_evidence=int(thresholds.get("faq_min_evidence", 1)),
            context_token_budget=int(thresholds.get("context_token_budget", 1200)),
            curiosity_min_observations=int(thresholds.get("curiosity_min_observations", 2)),
            documentation_draft_min_confidence=float(
                thresholds.get("documentation_draft_min_confidence", 0.75)
            ),
            documentation_task_min_confidence=float(
                thresholds.get("documentation_task_min_confidence", 0.4)
            ),
            current_state_boost=float(weights.get("current_state_boost", 2.0)),
            episodic_penalty=float(weights.get("episodic_penalty", 1.5)),
        )

    @classmethod
    def default(cls) -> WeightProfile:
        try:
            from weight_profiles import get_active_profile_id, load_profile

            return cls.from_catalog(load_profile(get_active_profile_id()))
        except Exception:  # noqa: BLE001 — keep hardcoded baseline if catalog missing
            return cls(
                profile_id="default-memory-profile",
                version=1,
                semantic_weight=3.0,
                episodic_weight=1.0,
                working_weight=2.0,
                evidence_weight=1.5,
                recency_weight=0.25,
                min_relevance_score=2.0,
                faq_min_observations=2,
                faq_min_evidence=1,
                context_token_budget=1200,
                curiosity_min_observations=2,
                documentation_draft_min_confidence=0.75,
                documentation_task_min_confidence=0.4,
                current_state_boost=2.0,
                episodic_penalty=1.5,
            )


@dataclass
class MemoryItem:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    kind: MemoryKind
    state: MemoryState
    title: str
    body: str
    tags: list[str]
    evidence_refs: list[str]
    source_refs: list[str]
    confidence: float
    created_at: str
    updated_at: str
    version: int = 1
    pinned: bool = False
    expires_at: str | None = None

    def activate(self, at: str) -> None:
        if self.state not in {MemoryState.CANDIDATE, MemoryState.STALE}:
            raise ConflictError("only candidate or stale memory can be activated")
        self.state = MemoryState.ACTIVE
        self.updated_at = at
        self.version += 1

    def mark_stale(self, at: str, reason: str) -> None:
        if self.state not in {MemoryState.ACTIVE, MemoryState.CANDIDATE}:
            raise ConflictError("only active or candidate memory can become stale")
        self.state = MemoryState.STALE
        self.updated_at = at
        self.version += 1
        self.tags = sorted(set([*self.tags, "stale:" + slug(reason)]))

    def promote_long_term(self, at: str, reason: str) -> None:
        """Promote working/episodic (or active candidate) into durable semantic memory."""
        if self.kind == MemoryKind.RESTRICTED or self.state == MemoryState.RESTRICTED:
            raise ConflictError("restricted memory cannot be promoted to long-term")
        if self.state in {MemoryState.DEPRECATED, MemoryState.ARCHIVED}:
            raise ConflictError("forgotten memory cannot be promoted")
        self.kind = MemoryKind.SEMANTIC
        if self.state in {MemoryState.CANDIDATE, MemoryState.STALE}:
            self.state = MemoryState.ACTIVE
        self.expires_at = None
        self.updated_at = at
        self.version += 1
        self.tags = sorted(set([*self.tags, "promoted:" + slug(reason)]))

    def deprecate(self, at: str, reason: str) -> None:
        """Soft-forget: keep searchable history, exclude from default prompts."""
        if self.kind == MemoryKind.RESTRICTED or self.state == MemoryState.RESTRICTED:
            raise ConflictError("restricted memory cannot be deprecated through this path")
        if self.state in {MemoryState.DEPRECATED, MemoryState.ARCHIVED}:
            raise ConflictError("memory is already forgotten")
        self.state = MemoryState.DEPRECATED
        self.updated_at = at
        self.version += 1
        self.tags = sorted(set([*self.tags, "deprecated:" + slug(reason)]))

    def is_expired(self, at: str | None = None) -> bool:
        if not self.expires_at:
            return False
        return parse_timestamp(self.expires_at) <= parse_timestamp(at or now())

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "project_group_id": self.scope.project_group_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "kind": self.kind.value,
            "state": self.state.value,
            "title": self.title,
            "body": self.body,
            "tags": self.tags,
            "evidence_refs": self.evidence_refs,
            "source_refs": self.source_refs,
            "confidence": self.confidence,
            "pinned": self.pinned,
            "expires_at": self.expires_at,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class QuestionMemory:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    normalized_question: str
    observations: int
    evidence_refs: list[str]
    state: QuestionState
    answer: str | None
    created_at: str
    updated_at: str
    version: int = 1

    def observe(self, evidence_refs: list[str], at: str) -> None:
        self.observations += 1
        self.evidence_refs = sorted(set([*self.evidence_refs, *evidence_refs]))
        self.updated_at = at
        self.version += 1

    def approve_faq(self, answer: str, profile: WeightProfile, at: str) -> None:
        if self.observations < profile.faq_min_observations or len(self.evidence_refs) < profile.faq_min_evidence:
            raise ConflictError("FAQ promotion requires repeated observations and evidence")
        self.answer = answer
        self.state = QuestionState.APPROVED_FAQ
        self.updated_at = at
        self.version += 1

    def curiosity_score(self) -> float:
        # Linear observation score; replace with a full weighted curiosity profile when needed.
        unresolved = 1.0 if self.state not in {QuestionState.APPROVED_FAQ, QuestionState.DRAFT_GENERATED} else 0.0
        evidence = min(len(self.evidence_refs), 3) * 0.5
        return round(float(self.observations) + unresolved + evidence, 3)

    def resolve_documentation(self, confidence: float, draft_content: str | None, profile: WeightProfile, at: str) -> str:
        if confidence < 0 or confidence > 1:
            raise ValidationError("confidence must be between 0 and 1")
        if confidence >= profile.documentation_draft_min_confidence:
            if not draft_content or not draft_content.strip():
                raise ValidationError("draft_content is required for documentation draft outcomes")
            self.answer = draft_content
            self.state = QuestionState.DRAFT_GENERATED
            outcome = "documentation_draft"
        elif confidence >= profile.documentation_task_min_confidence:
            self.answer = draft_content
            self.state = QuestionState.SEARCHING
            outcome = "task"
        else:
            self.answer = None
            self.state = QuestionState.BLOCKED_BY_GAP
            outcome = "knowledge_gap"
        self.updated_at = at
        self.version += 1
        return outcome

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "normalized_question": self.normalized_question,
            "observations": self.observations,
            "evidence_refs": self.evidence_refs,
            "state": self.state.value,
            "answer": self.answer,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class WorkBatch:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    title: str
    item_refs: list[str]
    deferred_actions: list[str]
    state: BatchState
    created_at: str
    updated_at: str
    version: int = 1

    def mark_ready(self, at: str, reason: str) -> None:
        if self.state not in {BatchState.OPEN, BatchState.ACTIVE}:
            raise ConflictError("only open or active batches can be marked ready")
        if not self.item_refs:
            raise ValidationError("batch requires item_refs before consolidation")
        self.state = BatchState.READY
        self.deferred_actions = sorted(set([*self.deferred_actions, "ready:" + slug(reason)]))
        self.updated_at = at
        self.version += 1

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "title": self.title,
            "item_refs": self.item_refs,
            "deferred_actions": self.deferred_actions,
            "state": self.state.value,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class ContextBundle:
    bundle_id: str
    scope: Scope
    query: str
    token_budget: int
    profile: WeightProfile
    items: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    built_at: str

    def public(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "query": self.query,
            "token_budget": self.token_budget,
            "weight_profile": {"profile_id": self.profile.profile_id, "version": self.profile.version},
            "prompt_cache": {"profile_id": self.profile.profile_id, "version": self.profile.version},
            "items": self.items,
            "excluded": self.excluded,
            "built_at": self.built_at,
        }
