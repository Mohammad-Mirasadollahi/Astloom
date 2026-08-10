---
doc_id: as.doc.ckg.decision-evidence-gate
title: 61 - Decision Evidence Gate
doc_type: feature_spec
status: draft
schema_version: '1.0'
owner: platform-product
summary: 'Future feature specification for `DecisionEvidenceGate` (impact×feasibility 5 × 5 = 25). Designed for later implementation over imperfect Neo4j code-graph + MCP agents.'
tags:
- feature-specification
- code-graph
- mcp
- imperfect-graph
- future
- decisionevidencegate
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/61-decision-evidence-gate.md
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
- as.doc.ckg.decision-evidence-gate
doc_version: 1.0.1
updated_at: 2026-08-10
---
# 61 - Decision Evidence Gate

## Implementation status

**Designed / not shipped.** Future-lane design transferred from the retired
research dump formerly at `docs/1.txt`. Do not treat as live product behavior.

## Purpose

Before every impact decision or edit, compile an explicit decision object of required claims and decide retrieve_more | targeted_read | targeted_sync | proceed | abstain per claim sufficiency — not node counts, average edge confidence, or model self-confidence.

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

Engineering judgment: **5 × 5 = 25** (impact × feasibility). Not a score
reported by cited papers.

## What to build

Implement `DecisionEvidenceGate` with operation-specific policies: architecture exploration may tolerate unsupported peripheral claims; destructive or security-sensitive edits cannot proceed while required claims remain unsupported. Claims examples: `target_symbol_uniquely_resolved`, `direct_callers_covered`, `registration_paths_checked`, `affected_tests_identified`, `source_read_for_low_confidence_claims`.

## Contract sketch

```json
{
  "operation": "edit_high_risk",
  "claims_required": [
    "target_symbol_uniquely_resolved",
    "direct_callers_covered",
    "registration_paths_checked",
    "affected_tests_identified",
    "source_read_for_low_confidence_claims"
  ],
  "claims_supported": [],
  "claims_unsupported": [],
  "conflicts": [],
  "freshness": {},
  "coverage_assumptions": [],
  "decision": "retrieve_more | targeted_read | targeted_sync | proceed | abstain"
}
```

## Primary decision flow

```mermaid
flowchart TD
  in[Operation + evidence] --> gate[DecisionEvidenceGate]
  gate -->|proceed| ok[Allow claim or action]
  gate -->|recover| rec[Targeted hybrid / read / sync]
  gate -->|abstain| stop[Abstain or escalate]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Agent / MCP | Collect structural and ancillary evidence | Inputs for the module |
| 2 | DecisionEvidenceGate | Apply module policy | proceed / recover / abstain |
| 3 | Agent | Act only within allowed decision | Safe next step |

## Failure modes attacked

FM1 missing edges; FM5 sparse retrieval; FM4 stale; FM6 multi-hop; FM7 miscalibration; FM8 ungrounded edits.

## Supporting sources

- Sufficient Context
- Selective QA under Domain Shift
- CS-RAG sufficiency-before-binding

## Dependencies / prerequisites

Task-risk taxonomy; claim schemas; source-span IDs; edge provenance; logged adjudicated outcomes.

## Eval metrics that would prove it works

- Unsafe-action rate at fixed coverage
- Risk–coverage and accuracy–coverage curves
- % high-risk decisions with every required claim supported
- False-abstention rate
- Calibration error for `P(decision_safe)` by language/framework/risk

## Risk if done wrong

Simplistic gate becomes another confidence threshold (blocks everything or permits unsafe actions). Training on agent self-judgments creates circular validation.

## Related Documents

- [`56-imperfect-graph-agent-decision-roadmap.md`](56-imperfect-graph-agent-decision-roadmap.md)
- [`57-imperfect-graph-failure-modes.md`](57-imperfect-graph-failure-modes.md)
- [`58-imperfect-graph-research-evidence-map.md`](58-imperfect-graph-research-evidence-map.md)
