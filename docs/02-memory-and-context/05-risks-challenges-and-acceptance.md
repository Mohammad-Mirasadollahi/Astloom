---
doc_id: as.doc.memory.risks-challenges-and-acceptance
title: Memory and Context - Risks, Challenges, and Acceptance
doc_type: gap
status: draft
schema_version: '1.0'
owner: platform-docs
summary: '- Over-consolidation can erase important evidence. - Old history can confuse agents
  if injected as current state. - Prompt caching requires stable ordering and versioning;
  small unnecessary changes can destroy cache hit rates. - RAG retrieval can miss critical
  rules unless graph .'
tags:
- gap
- memory
phase: 02-memory-and-context
canonical_path: docs/02-memory-and-context/05-risks-challenges-and-acceptance.md
lifecycle_lane: future
concern_lane: gap
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Memory and Context - Risks, Challenges, and Acceptance


## Purpose

- Over-consolidation can erase important evidence. - Old history can confuse agents if injected as current state. - Prompt caching requires stable ordering and versioning; small unnecessary changes can destroy cache hit rates. - RAG retrieval can miss critical rules unless graph .

## Challenges

- Over-consolidation can erase important evidence.
- Old history can confuse agents if injected as current state.
- Prompt caching requires stable ordering and versioning; small unnecessary changes can destroy cache hit rates.
- RAG retrieval can miss critical rules unless graph links and semantic search are combined.
- Memory decay must be conservative for security, compliance, and architectural decisions.

## Mitigation Strategy

- Keep raw evidence reachable through artifact references.
- Separate current state from historical events in schema and retrieval logic.
- Version static prompt sections and track invalidation reasons.
- Combine vector search with graph traversal and policy filters.
- Require owner review for deprecating high-risk semantic facts.

## Acceptance Criteria

- Agents receive current state by default and historical events only when relevant.
- Stable architecture context is versioned and cacheable across tasks.
- Deleted or deprecated code causes linked memory to be marked deprecated and excluded from default prompts.
- A task can request additional context through a retrieval interface with traceable sources.
