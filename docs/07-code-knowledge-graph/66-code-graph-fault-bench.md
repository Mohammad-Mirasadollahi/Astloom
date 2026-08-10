---
doc_id: as.doc.ckg.code-graph-fault-bench
title: 66 - Code Graph Fault Bench
doc_type: feature_spec
status: draft
schema_version: '1.0'
owner: platform-product
summary: 'Future feature specification for `CodeGraphFaultBench` (impact×feasibility 5 × 4 = 20). Designed for later implementation over imperfect Neo4j code-graph + MCP agents.'
tags:
- feature-specification
- code-graph
- mcp
- imperfect-graph
- future
- codegraphfaultbench
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/66-code-graph-fault-bench.md
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
- as.doc.ckg.code-graph-fault-bench
doc_version: 1.0.1
updated_at: 2026-08-10
---
# 66 - Code Graph Fault Bench

## Implementation status

**Designed / not shipped.** Future-lane design transferred from the retired
research dump formerly at `docs/1.txt`. Do not treat as live product behavior.

## Purpose

BRINK-style incompleteness and corruption harness over repositories with known call/import/configuration truth. Measure complete agent decisions, not only graph retrieval.

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

Inject: deleted exact edges; plausible false edges; ambiguous same-name targets; missing language adapters; dynamic registration ± traces; stale file versions; partial ingest/embedding loss; cross-language RPC gaps; truncated traversal; renamed symbols (anti-memorization). Compare structural-only, fixed fallback, sufficiency-gated, iterative recovery.

## Contract sketch

```text
FaultClass ∈ {
  delete_exact_edge, add_false_edge, ambiguous_name,
  missing_adapter, dynamic_reg, stale_file, partial_ingest,
  embedding_loss, rpc_gap, truncate_traversal, rename_symbol
}
Metric focus = unsafe_action_rate @ coverage
```

## Primary decision flow

```mermaid
flowchart TD
  in[Operation + evidence] --> gate[CodeGraphFaultBench]
  gate -->|proceed| ok[Allow claim or action]
  gate -->|recover| rec[Targeted hybrid / read / sync]
  gate -->|abstain| stop[Abstain or escalate]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Agent / MCP | Collect structural and ancillary evidence | Inputs for the module |
| 2 | CodeGraphFaultBench | Apply module policy | proceed / recover / abstain |
| 3 | Agent | Act only within allowed decision | Safe next step |

## Failure modes attacked

All FM1–FM8, especially silent incompleteness and parametric substitution.

## Supporting sources

- BRINK
- Missing-edge ECOOP
- PyCG precision/recall

## Dependencies / prerequisites

Fixtures; ground-truth oracles; mutation tooling; isolated Neo4j/Postgres scopes; task-level evaluation.

## Eval metrics that would prove it works

- Degradation curves vs deletion/noise
- Unsafe action vs graph completeness
- Recovery recall / unsupported-claim rate
- Risk–coverage per fault class
- Parametric-leakage score (rename/synthetic)
- Latency/cost per recovered task

## Risk if done wrong

Synthetic faults may be too easy; include production audit-log failures; hold out repos/frameworks.

## Related Documents

- [`56-imperfect-graph-agent-decision-roadmap.md`](56-imperfect-graph-agent-decision-roadmap.md)
- [`57-imperfect-graph-failure-modes.md`](57-imperfect-graph-failure-modes.md)
- [`58-imperfect-graph-research-evidence-map.md`](58-imperfect-graph-research-evidence-map.md)
