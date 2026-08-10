---
doc_id: as.doc.ckg.evidence-route-policy
title: 68 - Evidence Route Policy
doc_type: feature_spec
status: draft
schema_version: '1.0'
owner: platform-product
summary: 'Future feature specification for `EvidenceRoutePolicy` (impact×feasibility 4 × 3 = 12). Designed for later implementation over imperfect Neo4j code-graph + MCP agents.'
tags:
- feature-specification
- code-graph
- mcp
- imperfect-graph
- future
- evidenceroutepolicy
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/68-evidence-route-policy.md
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
- as.doc.ckg.evidence-route-policy
doc_version: 1.0.1
updated_at: 2026-08-10
---
# 68 - Evidence Route Policy

## Implementation status

**Designed / not shipped.** Future-lane design transferred from the retired
research dump formerly at `docs/1.txt`. Do not treat as live product behavior.

## Purpose

Train or calibrate a lightweight router from observed task outcomes to choose structural, narrow hybrid, iterative multi-hop, targeted read, targeted sync, build/static check, existing-test runtime trace, or abstention/human escalation.

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

Engineering judgment: **4 × 3 = 12** (impact × feasibility). Not a score
reported by cited papers.

## What to build

Inputs: operation risk, graph result status, edge provenance, unresolved-frontier size, freshness, language coverage, retriever score distribution, query type, previous tool outcomes, expected cost. Start with interpretable rules + offline replay; promote to learned policy only after reliable labels. High-risk safeguards override router.

## Contract sketch

```text
Route ∈ {
  structural, narrow_hybrid, iterative_multihop,
  targeted_read, targeted_sync, build_static_check,
  runtime_trace, abstain_or_human
}
```

## Primary decision flow

```mermaid
flowchart TD
  in[Operation + evidence] --> gate[EvidenceRoutePolicy]
  gate -->|proceed| ok[Allow claim or action]
  gate -->|recover| rec[Targeted hybrid / read / sync]
  gate -->|abstain| stop[Abstain or escalate]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Agent / MCP | Collect structural and ancillary evidence | Inputs for the module |
| 2 | EvidenceRoutePolicy | Apply module policy | proceed / recover / abstain |
| 3 | Agent | Act only within allowed decision | Safe next step |

## Failure modes attacked

Fixed fallback errors; FM5; unnecessary broad retrieval; tool loops; latency; wrong escalation.

## Supporting sources

- Adaptive-RAG
- Repoformer
- Toolformer

## Dependencies / prerequisites

Typed tool outcomes; task-success labels; cost telemetry; offline replay; high-risk overrides.

## Eval metrics that would prove it works

- Correct-route accuracy vs adjudicated oracle
- Task success per unit cost/latency
- Tool calls per successful task
- Wrong-source-read / unnecessary-sync rates
- OOD route failure by language/framework
- Unsafe route rate for high-risk actions

## Risk if done wrong

Labels may reward shallow-test passes; learned routers drift as analyzers/repos/models change.

## Related Documents

- [`56-imperfect-graph-agent-decision-roadmap.md`](56-imperfect-graph-agent-decision-roadmap.md)
- [`57-imperfect-graph-failure-modes.md`](57-imperfect-graph-failure-modes.md)
- [`58-imperfect-graph-research-evidence-map.md`](58-imperfect-graph-research-evidence-map.md)
