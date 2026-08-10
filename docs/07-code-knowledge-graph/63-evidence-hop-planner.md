---
doc_id: as.doc.ckg.evidence-hop-planner
title: 63 - Evidence Hop Planner
doc_type: feature_spec
status: draft
schema_version: '1.0'
owner: platform-product
summary: 'Future feature specification for `EvidenceHopPlanner` (impact×feasibility 5 × 4 = 20). Designed for later implementation over imperfect Neo4j code-graph + MCP agents.'
tags:
- feature-specification
- code-graph
- mcp
- imperfect-graph
- future
- evidencehopplanner
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/63-evidence-hop-planner.md
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
- as.doc.ckg.evidence-hop-planner
doc_version: 1.0.1
updated_at: 2026-08-10
---
# 63 - Evidence Hop Planner

## Implementation status

**Designed / not shipped.** Future-lane design transferred from the retired
research dump formerly at `docs/1.txt`. Do not treat as live product behavior.

## Purpose

Convert impact/edit questions into ordered evidence constraints; execute graph retrieval per hop; propagate bindings only when supported; for unsupported hops use hybrid or targeted source reads; never replace missing graph relations with LLM-proposed edges.

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

Engineering judgment: **5 × 4 = 20** (impact × feasibility). Not a score
reported by cited papers.

## What to build

Plan templates for common ops, e.g. H1 resolve symbol; H2 direct dependents; H3 registration/dispatch; H4 runtime entry points; H5 validation/build/test obligations. Free-form hops are hypotheses.

## Contract sketch

```text
H1: resolve changed symbol exactly
H2: enumerate direct structural dependents
H3: identify registration/dispatch mechanism
H4: connect dependents to runtime entry points
H5: identify validation/build/test obligations
```

## Primary decision flow

```mermaid
flowchart TD
  in[Operation + evidence] --> gate[EvidenceHopPlanner]
  gate -->|proceed| ok[Allow claim or action]
  gate -->|recover| rec[Targeted hybrid / read / sync]
  gate -->|abstain| stop[Abstain or escalate]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Agent / MCP | Collect structural and ancillary evidence | Inputs for the module |
| 2 | EvidenceHopPlanner | Apply module policy | proceed / recover / abstain |
| 3 | Agent | Act only within allowed decision | Safe next step |

## Failure modes attacked

FM1 missing edges; retrieval drift; FM6 multi-hop; cross-language gaps; unsupported structural continuation.

## Supporting sources

- CS-RAG
- PullNet
- IRCoT

## Dependencies / prerequisites

Typed absence (`62`); query-plan state store; source-span retrieval; deterministic symbol anchoring.

## Eval metrics that would prove it works

- Evidence-chain recall under 1%/5%/10%/20% edge deletion
- Unsupported-binding rate
- Invented intermediate dependency rate
- Retrieval calls/latency per correct chain
- Exact source-span recall for recovered hops

## Risk if done wrong

LLM decomposition can omit essential hops; keep deterministic templates.

## Related Documents

- [`56-imperfect-graph-agent-decision-roadmap.md`](56-imperfect-graph-agent-decision-roadmap.md)
- [`57-imperfect-graph-failure-modes.md`](57-imperfect-graph-failure-modes.md)
- [`58-imperfect-graph-research-evidence-map.md`](58-imperfect-graph-research-evidence-map.md)
