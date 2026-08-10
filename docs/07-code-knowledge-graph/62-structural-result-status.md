---
doc_id: as.doc.ckg.structural-result-status
title: 62 - Structural Result Status
doc_type: feature_spec
status: draft
schema_version: '1.0'
owner: platform-product
summary: 'Future feature specification for `StructuralResultStatus` (impact×feasibility 4 × 5 = 20). Designed for later implementation over imperfect Neo4j code-graph + MCP agents.'
tags:
- feature-specification
- code-graph
- mcp
- imperfect-graph
- future
- structuralresultstatus
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/62-structural-result-status.md
lifecycle_lane: future
concern_lane: design
audience_lane:
- platform-engineering
- platform-product
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.ckg.imperfect-graph-agent-decision-roadmap
- as.doc.ckg.imperfect-graph-failure-modes
- as.doc.ckg.imperfect-graph-research-evidence-map
- as.doc.ckg.imperfect-graph-policy-challenges
- as.doc.ckg.imperfect-graph-deferred-capabilities
- as.doc.ckg.metadata-first-code-understanding
- as.doc.ckg.context-pack-retrieval-and-agent-workflow
- as.doc.ckg.call-graph-confidence
- as.doc.ckg.codebase-memory-neo4j-hybrid-feature-spec
- as.doc.ckg.structural-result-status
doc_version: 1.0.1
updated_at: 2026-08-10
---
# 62 - Structural Result Status

## Implementation status

**Designed / not shipped.** Future-lane design transferred from the retired
research dump formerly at `docs/1.txt`. Do not treat as live product behavior.

## Purpose

Make “nothing found” diagnostically meaningful: every structural MCP tool returns typed `result_status`, `empty_reason`, coverage, unresolved frontier, and machine-readable `recommended_next_action`. `escalate_hint` becomes deterministic diagnosis, not “try hybrid”.

## Document flow

```mermaid
flowchart TD
  reader[Reader] --> doc[This document]
  doc --> road[56 roadmap]
  doc --> impl[Future implementation]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Reader | Opens this module | Understands scope and non-goals |
| 2 | Reader | Follows primary flow Mermaid + table | Sees intended decision path |
| 3 | Implementer | Uses contracts + acceptance | Builds and verifies the module |

## Rank and scoring

Engineering judgment: **4 × 5 = 20** (impact × feasibility). Not a score
reported by cited papers.

## What to build

Extend structural MCP responses. `complete_empty` may support a negative conclusion; `incomplete_empty` must not. Cover reasons: no_seed, unsupported_language, unresolved_dispatch, stale_scope, partial_ingest, traversal_limit, excluded_external, no_path_under_constraints, tool_error.

## Contract sketch

```json
{
  "result_status": "complete_empty | incomplete_empty | sparse | partial | error",
  "empty_reason": "none | no_seed | unsupported_language | unresolved_dispatch | stale_scope | partial_ingest | traversal_limit | excluded_external | no_path_under_constraints | tool_error",
  "coverage": {
    "files_expected": 120,
    "files_indexed": 118,
    "languages_supported": ["python"],
    "unsupported_constructs_seen": 7,
    "truncated": false
  },
  "unresolved_frontier": [],
  "recommended_next_action": "hybrid_query | source_read | targeted_sync | runtime_trace | abstain"
}
```

## Primary decision flow

```mermaid
flowchart TD
  in[Operation + evidence] --> gate[StructuralResultStatus]
  gate -->|proceed| ok[Allow claim or action]
  gate -->|recover| rec[Targeted hybrid / read / sync]
  gate -->|abstain| stop[Abstain or escalate]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Agent / MCP | Collect structural and ancillary evidence | Inputs for the module |
| 2 | StructuralResultStatus | Apply module policy | proceed / recover / abstain |
| 3 | Agent | Act only within allowed decision | Safe next step |

## Failure modes attacked

FM1 missing edges; FM3 dynamics; FM5 empty retrieval; partial ingest; overconfident negative impact.

## Supporting sources

- Soundiness manifesto
- Missing-edge ECOOP 2022
- PyCG precision/recall separation

## Dependencies / prerequisites

Analyzer capability registry; ingestion accounting; truncation metadata; stable MCP schema.

## Eval metrics that would prove it works

- `empty_reason` accuracy vs injected causes
- % empty results triggering correct next action
- Unsafe “no impact” rate after incomplete-empty
- Extra latency/tool calls per correct diagnosis

## Risk if done wrong

Emitting `complete_empty` without completeness proof encodes false certainty worse than today’s banner.

## Related Documents

- [`56-imperfect-graph-agent-decision-roadmap.md`](56-imperfect-graph-agent-decision-roadmap.md)
- [`57-imperfect-graph-failure-modes.md`](57-imperfect-graph-failure-modes.md)
- [`58-imperfect-graph-research-evidence-map.md`](58-imperfect-graph-research-evidence-map.md)
