---
doc_id: as.doc.ckg.uncertainty-aware-code-plan
title: 67 - Uncertainty Aware Code Plan
doc_type: feature_spec
status: draft
schema_version: '1.0'
owner: platform-product
summary: 'Future feature specification for `UncertaintyAwareCodePlan` (impact×feasibility 5 × 3 = 15). Designed for later implementation over imperfect Neo4j code-graph + MCP agents.'
tags:
- feature-specification
- code-graph
- mcp
- imperfect-graph
- future
- uncertaintyawarecodeplan
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/67-uncertainty-aware-code-plan.md
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
- as.doc.ckg.uncertainty-aware-code-plan
doc_version: 1.0.1
updated_at: 2026-08-10
---
# 67 - Uncertainty Aware Code Plan

## Implementation status

**Designed / not shipped.** Future-lane design transferred from the retired
research dump formerly at `docs/1.txt`. Do not treat as live product behavior.

## Purpose

Represent repository editing as a persistent plan graph. After each material edit: reparse, update structural relations, recompute may-impact, re-evaluate remaining steps, run narrowest deterministic checks, stop/branch when ambiguous dependencies exceed policy.

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

Engineering judgment: **5 × 3 = 15** (impact × feasibility). Not a score
reported by cited papers.

## What to build

Never let the initial graph snapshot define the complete edit set for a long-running change. Each step states target, evidence, assumptions, obligations, unresolved dependencies.

## Contract sketch

```text
PlanStep = {
  target, evidence_refs, assumptions,
  affected_obligations, unresolved_deps, status
}
on_material_edit -> reparse -> update_edges -> may_impact -> replan -> checks
```

## Primary decision flow

```mermaid
flowchart TD
  in[Operation + evidence] --> gate[UncertaintyAwareCodePlan]
  gate -->|proceed| ok[Allow claim or action]
  gate -->|recover| rec[Targeted hybrid / read / sync]
  gate -->|abstain| stop[Abstain or escalate]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Agent / MCP | Collect structural and ancillary evidence | Inputs for the module |
| 2 | UncertaintyAwareCodePlan | Apply module policy | proceed / recover / abstain |
| 3 | Agent | Act only within allowed decision | Safe next step |

## Failure modes attacked

Staleness during editing; missed downstream files; FM6; plan drift; ungrounded edits.

## Supporting sources

- CodePlan
- SWE-agent interface
- Monitor-Guided Decoding

## Dependencies / prerequisites

Fast incremental ingest; idempotent invalidation; plan persistence; revision pinning; deterministic test/build tools.

## Eval metrics that would prove it works

- Repo tasks passing build/test/semantic validity
- Required-file recall / unnecessary-file precision vs oracle
- Plan revisions from newly discovered evidence
- Regressions per successful task
- Cost/latency vs one-shot planning

## Risk if done wrong

Replanning can amplify false deps into edit cascades; expansions must keep provenance/confidence.

## Related Documents

- [`56-imperfect-graph-agent-decision-roadmap.md`](56-imperfect-graph-agent-decision-roadmap.md)
- [`57-imperfect-graph-failure-modes.md`](57-imperfect-graph-failure-modes.md)
- [`58-imperfect-graph-research-evidence-map.md`](58-imperfect-graph-research-evidence-map.md)
