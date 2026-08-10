---
doc_id: as.doc.ckg.gap-diagnosis-pipeline
title: 69 - Gap Diagnosis Pipeline
doc_type: feature_spec
status: draft
schema_version: '1.0'
owner: platform-product
summary: 'Future feature specification for `GapDiagnosisPipeline` (impact×feasibility 4 × 3 = 12). Designed for later implementation over imperfect Neo4j code-graph + MCP agents.'
tags:
- feature-specification
- code-graph
- mcp
- imperfect-graph
- future
- gapdiagnosispipeline
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/69-gap-diagnosis-pipeline.md
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
- as.doc.ckg.gap-diagnosis-pipeline
doc_version: 1.0.1
updated_at: 2026-08-10
---
# 69 - Gap Diagnosis Pipeline

## Implementation status

**Designed / not shipped.** Future-lane design transferred from the retired
research dump formerly at `docs/1.txt`. Do not treat as live product behavior.

## Purpose

When graph and source disagree, create persistent gap cases with call site, relation class, analyzer coverage, candidates, language feature, build context, and runtime observations; classify root causes; store runtime-observed edges as scoped observations, not universal exact.

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

Cause classes: dynamic/reflection; DI/registration; generated code; external framework callback; import/build config; cross-language/RPC; parser failure; scope exclusion; stale/partial index. Safe traces from existing tests or controlled executions where allowed.

## Contract sketch

```text
GapCase = {
  call_site, expected_rel, coverage, candidates,
  language_feature, build_context, runtime_obs[],
  root_cause_hypothesis, status
}
```

## Primary decision flow

```mermaid
flowchart TD
  in[Operation + evidence] --> gate[GapDiagnosisPipeline]
  gate -->|proceed| ok[Allow claim or action]
  gate -->|recover| rec[Targeted hybrid / read / sync]
  gate -->|abstain| stop[Abstain or escalate]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Agent / MCP | Collect structural and ancillary evidence | Inputs for the module |
| 2 | GapDiagnosisPipeline | Apply module policy | proceed / recover / abstain |
| 3 | Agent | Act only within allowed decision | Safe next step |

## Failure modes attacked

FM3 dynamics; recurrent missing edges; passive knowledge gaps; cross-language; analyzer blind spots.

## Supporting sources

- Missing-edge ECOOP
- PyCG
- Approximate JS CG (useful when assumptions explicit)

## Dependencies / prerequisites

Gap persistence; test-run provenance; safe execution env; static/dynamic namespaces; analyzer capability metadata.

## Eval metrics that would prove it works

- % recurring gaps with correct root cause
- Reduction in repeated escalations for same construct
- Edge recall after analyzer remediation
- False universalization of runtime-observed edges
- Mean time first gap → deterministic repair

## Risk if done wrong

Dynamic traces mistaken for complete behavior; tests cover subsets of paths/envs/plugins.

## Related Documents

- [`56-imperfect-graph-agent-decision-roadmap.md`](56-imperfect-graph-agent-decision-roadmap.md)
- [`57-imperfect-graph-failure-modes.md`](57-imperfect-graph-failure-modes.md)
- [`58-imperfect-graph-research-evidence-map.md`](58-imperfect-graph-research-evidence-map.md)
