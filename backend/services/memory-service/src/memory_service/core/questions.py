"""Question / FAQ / documentation commands."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .enums import QuestionState
from .helpers import documentation_outcome, normalize_question, now, sanitize
from .models import QuestionMemory, Scope


class QuestionCommands:
    def observe_question(self, scope: Scope, actor: str, correlation_id: str, key: str, question: str, evidence_refs: list[str]) -> QuestionMemory:
        self._require_key(key)
        normalized = normalize_question(question)
        payload = {"normalized_question": normalized, "evidence_refs": sorted(set(sanitize(evidence_refs)))}
        prior = self.store.idempotent(scope, "observe_question", key, payload)
        if prior:
            return self.store.get_question(prior, scope)
        timestamp = now()
        item = self.store.find_question(normalized, scope)
        if item:
            item.observe(payload["evidence_refs"], timestamp)
        else:
            item = QuestionMemory(str(uuid4()), scope, actor, correlation_id, normalized, 1, payload["evidence_refs"], QuestionState.OBSERVED, None, timestamp, timestamp)
        self.store.put_question(item)
        self.store.remember(scope, "observe_question", key, payload, item.id)
        self.emit("QuestionObserved", item.public(), scope, actor, correlation_id, key, item.id, item.evidence_refs)
        return item

    def promote_faq(self, scope: Scope, actor: str, correlation_id: str, key: str, question_id: str, answer: str) -> QuestionMemory:
        self._require_key(key)
        payload = {"question_id": question_id, "answer": sanitize(answer)}
        prior = self.store.idempotent(scope, "promote_faq", key, payload)
        if prior:
            return self.store.get_question(prior, scope)
        item = self.store.get_question(question_id, scope)
        item.approve_faq(payload["answer"], self.profile, now())
        self.store.put_question(item)
        self.store.remember(scope, "promote_faq", key, payload, item.id)
        self.emit("FAQPromoted", item.public(), scope, actor, correlation_id, key, item.id, item.evidence_refs)
        return item

    def resolve_missing_documentation(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        question_id: str,
        confidence: float,
        draft_content: str | None = None,
    ) -> dict[str, Any]:
        self._require_key(key)
        payload = {
            "question_id": question_id,
            "confidence": confidence,
            "draft_content": sanitize(draft_content) if draft_content is not None else None,
        }
        prior = self.store.idempotent(scope, "resolve_missing_documentation", key, payload)
        if prior:
            item = self.store.get_question(prior, scope)
            return {
                "question_memory": item.public(),
                "outcome": documentation_outcome(item.state),
                "curiosity_score": item.curiosity_score(),
            }
        item = self.store.get_question(question_id, scope)
        outcome = item.resolve_documentation(confidence, payload["draft_content"], self.profile, now())
        self.store.put_question(item)
        self.store.remember(scope, "resolve_missing_documentation", key, payload, item.id)
        event_type = {
            "documentation_draft": "DocumentationDraftCreated",
            "task": "DocumentationTaskSuggested",
            "knowledge_gap": "KnowledgeGapCreated",
        }[outcome]
        result = {
            "question_memory": item.public(),
            "outcome": outcome,
            "curiosity_score": item.curiosity_score(),
        }
        self.emit(event_type, result, scope, actor, correlation_id, key, item.id, item.evidence_refs)
        return result

    def list_repeated_questions(self, scope: Scope) -> list[QuestionMemory]:
        return [item for item in self.store.list_questions(scope) if item.observations >= self.profile.faq_min_observations]

    def list_curious_questions(self, scope: Scope) -> list[dict[str, Any]]:
        curious = []
        for item in self.store.list_questions(scope):
            score = item.curiosity_score()
            if item.observations >= self.profile.curiosity_min_observations and score >= float(self.profile.curiosity_min_observations):
                payload = item.public()
                payload["curiosity_score"] = score
                curious.append(payload)
        return curious
