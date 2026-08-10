---
doc_id: as.doc.memory.autonomous-question-discovery-and-faq-memory-continued
title: 07 - Autonomous Question Discovery And FAQ Memory (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/02-memory-and-context/07-autonomous-question-discovery-and-faq-memory.md`
  — remaining sections after the soft size budget.
tags:
- standard
- memory
phase: 02-memory-and-context
canonical_path: docs/02-memory-and-context/07-autonomous-question-discovery-and-faq-memory-continued.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 07 - Autonomous Question Discovery And FAQ Memory (Continued)

## Purpose

Continuation of `docs/02-memory-and-context/07-autonomous-question-discovery-and-faq-memory.md` — remaining sections after the soft size budget.

## Curiosity Policy

Curiosity must be useful and bounded.

The system may investigate proactively when:

- a question repeats frequently.
- a question blocks task completion.
- a question concerns high-risk code.
- a missing doc affects public API or ownership.
- a human explicitly asks the system to learn it.
- repeated token cost is high.

The system should defer or ignore curiosity when:

- the question is one-off and low risk.
- the question is outside scope.
- required permissions are missing.
- active work should not be interrupted.
- evidence search would be too expensive for current priority.

## Human Feedback And Correction

Human correction should update future behavior.

Correction types:

- answer is wrong.
- answer is outdated.
- answer scope is wrong.
- evidence is weak.
- generated documentation is wrong.
- question normalization grouped unrelated questions.
- FAQ promotion is not useful.

A correction should:

- create a feedback record.
- lower confidence or supersede answer.
- update normalization examples when needed.
- create a new Task or Gap when needed.
- update scoring features.
- appear in audit history.

## Product Experience

The web interface should expose a Question Intelligence view.

Views:

- repeated questions.
- unanswered questions.
- questions needing investigation.
- questions with missing documentation.
- documentation drafts from questions.
- FAQ candidates.
- stale answers.
- blocked gaps.
- corrected answers.

Actions:

- approve FAQ.
- reject FAQ.
- edit answer.
- request investigation.
- create documentation task.
- create gap.
- mark low value.
- split normalized question.
- merge duplicate questions.
- change owner.
- pin project FAQ.

## Example Flow: Missing Function Documentation

Initial state:

- multiple agents ask what validate_access_scope does.
- no documentation anchor exists for the symbol.
- code graph shows the function is called from authorization middleware.

System flow:

1. records QuestionObservation for each question.
2. normalizes to Documentation and purpose for symbol validate_access_scope.
3. increases curiosity_score because the question repeats and affects authorization.
4. queries docs graph and finds no anchor.
5. queries code graph, tests, decisions, and work logs.
6. determines evidence is sufficient for a draft but high-risk because authorization is involved.
7. creates DocumentationDraft with confidence and evidence.
8. creates Task for security owner review.
9. stores QuestionMemory as documentation_missing and waiting_for_review.
10. after review, publishes documentation and promotes scoped project FAQ.

## Example Flow: Stable Repeated Answer

Initial state:

- several developers ask which event is emitted after memory consolidation.
- docs already answer the question.
- answer has been reused successfully.

System flow:

1. records observations.
2. normalizes question to Event emitted after memory consolidation.
3. finds documented answer memory.consolidation_completed.
4. raises FAQ score due repetition and stable evidence.
5. promotes project FAQ after scope check.
6. future agents receive the FAQ answer with source links and low token cost.

## Acceptance Criteria

This design is acceptable when:

- repeated questions are detected, normalized, scoped, and scored.
- curiosity is configurable, bounded, and explainable.
- unanswered questions trigger evidence search before answer generation.
- missing documentation can result in existing-doc answer, stale-doc finding, documentation draft, Task, or KnowledgeGap.
- FAQ memory promotion requires evidence, confidence, freshness, low correction rate, and scope isolation checks.
- human corrections update answer confidence, normalization, scoring, and future retrieval.
- project-specific knowledge is not shared outside scope by default.
- every generated answer or documentation draft includes evidence, confidence, owner, scope, and review status.


## Related Documents

- Parent document: `docs/02-memory-and-context/07-autonomous-question-discovery-and-faq-memory.md`
