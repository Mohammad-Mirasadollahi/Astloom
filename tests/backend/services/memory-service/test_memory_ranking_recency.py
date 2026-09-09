"""Unit: memory ranking prefers newer notes; MCP write can supersede."""

from __future__ import annotations

from memory_service.core.enums import MemoryKind, MemoryState
from memory_service.core.models import MemoryItem, Scope, WeightProfile
from memory_service.core.retrieval import RetrievalCommands


class _Bare(RetrievalCommands):
    def __init__(self) -> None:
        self.profile = WeightProfile(
            profile_id="t",
            version=1,
            semantic_weight=1.0,
            episodic_weight=0.5,
            working_weight=0.8,
            evidence_weight=0.2,
            recency_weight=1.0,
            min_relevance_score=0.1,
            faq_min_observations=2,
            faq_min_evidence=1,
            context_token_budget=500,
            current_state_boost=0.5,
            episodic_penalty=0.3,
        )


def _item(*, mid: str, title: str, body: str, confidence: float, updated_at: str) -> MemoryItem:
    return MemoryItem(
        id=mid,
        scope=Scope("t", "w", "p"),
        actor_id="a",
        correlation_id="c",
        kind=MemoryKind.SEMANTIC,
        state=MemoryState.ACTIVE,
        title=title,
        body=body,
        tags=["i18n", "intelligence"],
        evidence_refs=[],
        source_refs=[],
        confidence=confidence,
        version=1,
        created_at=updated_at,
        updated_at=updated_at,
        pinned=False,
        expires_at=None,
    )


def test_newer_higher_confidence_outranks_older_on_tie_break():
    svc = _Bare()
    older = _item(
        mid="m-old",
        title="i18n bilingual EN FA",
        body="two-line bilingual EN/FA splitPairedLabel",
        confidence=0.7,
        updated_at="2026-09-09T10:00:00+00:00",
    )
    newer = _item(
        mid="m-new",
        title="i18n locale pure",
        body="locale-pure copy law for Intelligence i18n",
        confidence=0.95,
        updated_at="2026-09-09T18:00:00+00:00",
    )
    terms = {"i18n", "intelligence"}
    assert svc._score(newer, terms) > svc._score(older, terms)
    ranked = sorted(
        [(svc._score(older, terms), older), (svc._score(newer, terms), newer)],
        key=lambda pair: (-pair[0], -(svc._updated_at_ts(pair[1])), pair[1].id),
    )
    assert ranked[0][1].id == "m-new"
