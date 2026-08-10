---
doc_id: as.doc.memory.index
title: 02 - Memory and Context Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: Give agents the right context at the right time while keeping prompts fast, cheap,
  current, scoped, and low-noise.
tags:
- index
- memory
phase: 02-memory-and-context
canonical_path: docs/02-memory-and-context/00-index.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.2.1
updated_at: 2026-08-10
---

# 02 - Memory and Context Index


## Purpose

Give agents the right context at the right time while keeping prompts fast, cheap, current, scoped, and low-noise.

## Mission

Give agents the right context at the right time while keeping prompts fast, cheap, current, scoped, and low-noise.

## Files

- 01-feature-specification.md defines memory features and functional requirements.
- 02-high-level-design.md defines actors, components, data flow, integrations, and reliability requirements.
- 03-low-level-design.md defines classification, consolidation, weighting, retrieval, decay, and prompt-packing logic.
- 04-data-contracts-and-events.md defines memory entities, events, and WeightProfile contracts.
- 05-risks-challenges-and-acceptance.md defines memory risks and acceptance criteria.
- 06-detailed-section-design.md provides deep rationale, memory lifecycle, retrieval design, edge cases, and phase output.
- 07-autonomous-question-discovery-and-faq-memory.md defines repeated question detection, curiosity scoring, missing documentation discovery, FAQ memory, evidence-backed answer promotion, and human-like knowledge gap handling.
- 08-batched-memory-and-deferred-knowledge-workflows.md defines WorkBatch, deferred memory consolidation, deferred documentation generation, deferred code review, LLM batching decisions, and boundary detection.
- 09-chat-qa-rag-incremental-documentation.md defines chat Q&A write-back into project RAG, retention of derived docs, freshness on code change, code-as-authority, and staged code-vs-doc contradiction disclosure.
- 10-chat-quality-prior-art-license-and-method.md defines license-verified OSS chat/RAG study method, clean-room policy, and index of quality idea catalogs.
- 11-chat-quality-retrieval-ranking-and-context-packing.md catalogs hybrid retrieval, rerank, RAPTOR/GraphRAG modes, thresholds, pins, and context budgets.
- 12-weight-profile-governance.md closes GAP-006: ownership, approval, activation, and rollback for WeightProfiles (CLI included).
- 12-chat-quality-grounding-citations-refusal.md catalogs grounding, citations, empty/query refusal, relevance warnings, and contradiction-stage alignment.
- 13-chat-quality-query-rewrite-memory-feedback.md catalogs query rewrite, keyword expansion, history fitting, chunk feedback, and branching.
- 13-context-bundle-audit-and-verification.md closes GAP-T04: ContextBundle audit schema, fail-closed verifier, and prompt-safety tests.
- 14-memory-browser-and-long-term-selection-ui.md specifies the human Memory Browser UI: list/filter memory, keep long-term, forget from prompts, pin, and preview ContextBundles (UI only; APIs in memory-service).

## Features Covered

- Three-Tier Memory.
- Memory Consolidation.
- State over Event Context.
- Decay and Garbage Collection.
- Human remember / forget (promote long-term, deprecate, working TTL, pin).
- Memory Browser UI (documented; implementation pending).
- Prompt Caching.
- Dynamic Context Injection and RAG.
- Configurable Memory Weighting.
- Autonomous Question Discovery.
- FAQ Memory.
- Curiosity Scoring.
- Missing Documentation Discovery.
- Batched Memory Consolidation.
- Deferred Documentation Generation.
- Deferred Code Review.
- Chat Q&A RAG Incremental Documentation.
- Code-vs-Doc Contradiction Disclosure.
- Chat Quality Prior Art (retrieval, grounding, rewrite/feedback).

## Related Technical Logic

- ../06-technical-logic/02-memory-context-technical-logic.md explains memory classification, consolidation, retrieval scoring, prompt cache invalidation, decay, token budgeting, question memory, FAQ scoring, curiosity scoring, and batched consolidation.

## Optional ANN Acceleration

- ../13-technology-stack-and-platform-decisions/08-turbovec-ann-acceleration-integration.md — ADR: turbovec beside pgvector SoR.
- ../13-technology-stack-and-platform-decisions/11-turbovec-for-rag.md — how to use turbovec in RAG pipelines.
- ../11-logical-implementation-examples/08-turbovec-hybrid-retrieval-example.md — hybrid allowlist retrieval example.
