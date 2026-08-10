---
doc_id: as.doc.memory.autonomous-question-discovery-and-faq-memory
title: 07 - Autonomous Question Discovery And FAQ Memory
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom should treat repeated questions, unanswered questions, and missing documentation
  as structured knowledge signals. The system should not only answer a question once. It should
  notice when a question keeps appearing, determine whether the answer already exists, investigat.
tags:
- standard
- memory
phase: 02-memory-and-context
canonical_path: docs/02-memory-and-context/07-autonomous-question-discovery-and-faq-memory.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
placeholder: 1
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 07 - Autonomous Question Discovery And FAQ Memory

## 07 - Autonomous Question Discovery And FAQ Memory
## Purpose

Astloom should treat repeated questions, unanswered questions, and missing documentation as structured knowledge signals. The system should not only answer a question once. It should notice when a question keeps appearing, determine whether the answer already exists, investigate why the answer is hard to find, generate or request documentation when evidence supports it, and promote stable answers into scoped FAQ memory.

The intended behavior is similar to a disciplined senior engineer or product-minded technical lead. When the same uncertainty appears repeatedly, the system should become curious in a controlled way: search evidence, inspect code and docs, identify the knowledge gap, create a draft answer or documentation task, and store the result with scope, confidence, freshness, and evidence.

Chat-turn write-back into RAG, retention of Q&A-derived docs, freshness on code change, and staged code-versus-documentation contradiction disclosure are specified in `09-chat-qa-rag-incremental-documentation.md`. This document owns curiosity scoring, FAQ promotion policy, and the broader evidence search loop.

Open-source chat/RAG quality levers (license-verified prior art) are indexed from `10-chat-quality-prior-art-license-and-method.md` and theme catalogs `11`–`13`.

## Corrected Requirement

The raw user requirement can be formalized as follows:

Astloom must maintain an autonomous question intelligence loop. When humans or agents repeatedly ask a question, or when a high-value question has no reliable answer, the system should normalize the question, score its importance, search available evidence, determine whether documentation or memory is missing, produce a supported answer or documentation draft when confidence is sufficient, create a Task or Gap when confidence is insufficient, and store the result as scoped knowledge that can be reused later.

This must be project-aware, evidence-backed, configurable, and reviewable. The system must not fabricate answers, must not globally share project-specific knowledge, and must not fill long-term memory with low-value one-off questions.

## Professional Audience

This design is written for:

- software engineers implementing memory, retrieval, code graph, docs sync, task, and audit services.
- product designers defining repeated-question UX, missing-doc workflows, review states, and operator controls.
- architects reviewing project isolation, scoring, contracts, and autonomous action boundaries.
- operators managing knowledge quality and gap resolution.
- security reviewers checking scope isolation and prompt safety.

## Problem Statement

Common recurring questions include:

- What does this function do.
- Why is there no documentation for this function.
- Which module owns this behavior.
- Which API contract should I use.
- Why did this rule block the change.
- Which memory item is current truth.
- Why was this task created.
- Is this answer still valid.
- Does this concept belong to project A or project B.

Without a structured loop, the system has bad outcomes:

- repeated token cost from answering the same question.
- repeated human frustration.
- stale or missing documentation remains hidden.
- agents rediscover the same facts.
- memory fills with unstructured question-answer fragments.
- answers are reused without evidence or scope checks.
- project-specific answers leak across unrelated projects.

## Goals

- Detect repeated and important questions.
- Normalize similar questions into canonical question records.
- Score curiosity, FAQ eligibility, urgency, and documentation impact.
- Search evidence across docs, code graph, decisions, work logs, tasks, tests, rules, and human feedback.
- Identify whether an answer exists, is stale, is missing, or needs review.
- Generate documentation drafts only when evidence is sufficient.
- Create Tasks or Gaps when evidence is insufficient.
- Store stable answers as scoped FAQ memory.
- Explain why a question was promoted, deferred, rejected, or escalated.
- Keep project data isolated by default.

## Non-Goals

- The system should not browse or inspect unrelated projects to answer scoped questions.
- The system should not generate authoritative documentation without evidence.
- The system should not promote every question to long-term memory.
- The system should not treat model confidence alone as evidence.
- The system should not share project FAQ memory globally unless explicitly approved and sanitized.
- The system should not interrupt active work for low-priority curiosity.

## Core Objects

### QuestionObservation

A QuestionObservation records one instance of a question being asked.

Fields:

- observation_id.
- raw_question.
- actor_ref.
- actor_type.
- workspace_id.
- project_id.
- project_group_id when applicable.
- task_ref.
- session_ref.
- source_surface.
- detected_entities.
- timestamp.
- retrieval_result_summary.
- answer_used_ref.
- correction_ref.

### QuestionMemory

QuestionMemory is the canonical normalized question object.

Fields:

- question_id.
- normalized_question.
- question_intent.
- scope.
- tenant_id.
- workspace_id.
- project_id.
- project_group_id when applicable.
- related_symbols.
- related_documents.
- related_decisions.
- related_tasks.
- related_rules.
- observation_count.
- distinct_actor_count.
- first_observed_at.
- last_observed_at.
- answer_status.
- current_answer_ref.
- evidence_refs.
- curiosity_score.
- faq_score.
- urgency_score.
- documentation_gap_score.
- confidence_score.
- freshness_score.
- sensitivity_level.
- owner.
- next_action.
- review_status.

### QuestionAnswer

QuestionAnswer stores a candidate or approved answer.

Fields:

- answer_id.
- question_id.
- answer_text.
- answer_type.
- scope.
- evidence_refs.
- generated_by.
- confidence_score.
- freshness_status.
- review_status.
- reviewer_ref.
- created_at.
- supersedes_answer_id.
- correction_count.
- reuse_count.

### KnowledgeGap

KnowledgeGap records that the system could not answer safely.

Fields:

- gap_id.
- question_id.
- gap_type.
- missing_evidence.
- affected_module.
- affected_symbol.
- impact.
- owner.
- recommended_action.
- linked_task_id.
- status.

### DocumentationDraft

DocumentationDraft records generated documentation that requires review or publication.

Fields:

- draft_id.
- question_id.
- target_doc_ref.
- target_symbol_ref.
- draft_content.
- evidence_refs.
- confidence_score.
- review_status.
- owner.
- created_task_id.

## Question Intent Classification

Question intent should be classified before retrieval.

Intent types:

- symbol_purpose.
- missing_documentation.
- module_ownership.
- contract_lookup.
- decision_rationale.
- rule_explanation.
- task_origin.
- memory_truth_check.
- project_scope_check.
- operational_status.
- onboarding_question.
- unknown.

Classification output should include:

- intent.
- confidence.
- detected_entities.
- required_evidence_types.
- safe_autonomy_level.

## State Machine

QuestionMemory should have explicit lifecycle states.

States:

- observed.
- normalized.
- candidate_repeated.
- needs_investigation.
- searching_evidence.
- answered_with_existing_evidence.
- documentation_missing.
- draft_generated.
- waiting_for_review.
- approved_faq.
- rejected_low_value.
- blocked_by_gap.
- stale_answer_detected.
- superseded.
- archived.

State transitions:

- observed to normalized when canonical form is created.
- normalized to candidate_repeated when thresholds are met.
- candidate_repeated to needs_investigation when curiosity score crosses threshold.
- needs_investigation to searching_evidence when investigation job starts.
- searching_evidence to answered_with_existing_evidence when sufficient evidence exists.
- searching_evidence to documentation_missing when no doc anchor or answer exists.
- documentation_missing to draft_generated when evidence supports draft generation.
- draft_generated to waiting_for_review when review is required.
- waiting_for_review to approved_faq when human or policy approval succeeds.
- any active state to blocked_by_gap when evidence is insufficient.
- approved_faq to stale_answer_detected when linked evidence changes.

## Evidence Search Pipeline

When a question requires investigation, Astloom should search evidence in a defined order.

Pipeline:

1. Apply tenant, workspace, project, and project group scope before retrieval.
2. Normalize the question and detect entities.
3. Query approved FAQ memory in the same scope.
4. Query active SemanticFacts and Decisions.
5. Query documentation anchors and docs graph.
6. Query code graph for symbols, call edges, ownership, and tests.
7. Query WorkLogs, Issues, Tasks, and recent batches.
8. Query rule evaluations when question concerns policy or approval.
9. Query human corrections and feedback records.
10. Score evidence strength and freshness.
11. Decide answer, draft, task, gap, or defer.

The system must record which evidence sources were checked and why high-ranking evidence was accepted or rejected.

## Missing Documentation Workflow

When the question concerns missing documentation for a function, class, API, rule, or workflow, the system should execute this workflow.

1. Resolve the referenced symbol or object.
2. Verify project scope and permission.
3. Query docs graph for an existing anchor.
4. If anchor exists, test freshness against code graph and recent decisions.
5. If anchor is missing, inspect symbol signature, call graph, tests, owners, and related decisions.
6. Determine whether evidence is sufficient for a draft.
7. Generate a documentation draft only if confidence exceeds configured threshold.
8. Create a Task for owner review if the target is public, security-sensitive, or high-risk.
9. Create a KnowledgeGap when evidence is insufficient.
10. Link the question, draft, task, and gap together.

The system should distinguish between:

- documentation exists and is valid.
- documentation exists but is stale.
- documentation does not exist but can be drafted.
- documentation does not exist and cannot be drafted safely.
- documentation should not exist because the symbol is private or generated.

## Scoring Model

Scoring must be configurable and versioned. Final weights must come from WeightProfile or QuestionIntelligenceProfile, not hard-coded constants.

Recommended score families:

- curiosity_score: should the system investigate.
- faq_score: should the answer become reusable FAQ memory.
- urgency_score: should the question interrupt current workflow.
- documentation_gap_score: does missing documentation need action.
- confidence_score: how reliable is the candidate answer.
- freshness_score: how current is the evidence.
- sensitivity_score: how risky is storage or sharing.

Example configurable formula:

    curiosity_score =
        repetition_weight +
        distinct_actor_weight +
        unresolved_status_weight +
        risk_weight +
        token_cost_weight +
        documentation_gap_weight +
        human_importance_weight -
        low_value_penalty -
        sensitivity_penalty

The explanation should list contributing factors, such as:

- asked 14 times across 5 sessions.
- asked by 4 distinct actors.
- no documentation anchor found for symbol.
- answer confidence is below threshold.
- repeated retrieval consumed high token budget.
- affected module is authentication.
- human marked the question as important.

## FAQ Promotion Policy

A question can become FAQ memory only when all required conditions pass.

Required conditions:

- answer is stable.
- answer has evidence references.
- answer scope is clear.
- answer is not sensitive beyond allowed scope.
- correction rate is below threshold.
- evidence is fresh enough.
- project isolation checks pass.
- owner or policy approval exists when required.

FAQ scopes:

- project FAQ.
- project group FAQ.
- workspace FAQ.
- sanitized global pattern FAQ.

Project-specific answers must not be promoted to workspace or global scope without explicit review.

## Related Documents

- Continued in `docs/02-memory-and-context/07-autonomous-question-discovery-and-faq-memory-continued.md`
