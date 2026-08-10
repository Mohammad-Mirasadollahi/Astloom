---
doc_id: as.doc.ckg.grounded-edit-packet
title: 70 - Grounded Edit Packet
doc_type: feature_spec
status: draft
schema_version: '1.0'
owner: platform-product
summary: 'Future feature specification for `GroundedEditPacket` (impact×feasibility 4 × 3 = 12). Designed for later implementation over imperfect Neo4j code-graph + MCP agents.'
tags:
- feature-specification
- code-graph
- mcp
- imperfect-graph
- future
- groundededitpacket
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/70-grounded-edit-packet.md
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
- as.doc.ckg.grounded-edit-packet
doc_version: 1.0.1
updated_at: 2026-08-10
---
# 70 - Grounded Edit Packet

## Implementation status

**Designed / not shipped.** Future-lane design transferred from the retired
research dump formerly at `docs/1.txt`. Do not treat as live product behavior.

## Purpose

Before applying an edit, produce a machine-readable packet binding each change to source spans, structural edges, eligibility/provenance, assumptions, unsupported claims, and expected compile/type/test obligations; after edit run independent checks. Generator self-critique is not independent evidence.

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

Verifier rejects claims lacking source span or deterministic derived fact. Independent checks: parser, compiler/type checker, repo static rules, affected tests, graph re-ingest.

## Contract sketch

```json
{
  "planned_changes": [],
  "source_spans_read": [],
  "edges_used": [],
  "edge_eligibility": [],
  "assumptions": [],
  "unsupported_claims": [],
  "obligations": ["compile", "types", "tests"]
}
```

## Primary decision flow

```mermaid
flowchart TD
  in[Operation + evidence] --> gate[GroundedEditPacket]
  gate -->|proceed| ok[Allow claim or action]
  gate -->|recover| rec[Targeted hybrid / read / sync]
  gate -->|abstain| stop[Abstain or escalate]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Agent / MCP | Collect structural and ancillary evidence | Inputs for the module |
| 2 | GroundedEditPacket | Apply module policy | proceed / recover / abstain |
| 3 | Agent | Act only within allowed decision | Safe next step |

## Failure modes attacked

FM8 hallucinated impact; edits unsupported by evidence; citation laundering; self-confirming loops.

## Supporting sources

- WebGPT references
- Monitor-Guided Decoding
- SWE-agent edit/test interface
- Sufficient Context

## Dependencies / prerequisites

Stable source-span IDs; edge provenance; deterministic tool outputs; revision pinning; verifier ≠ generator.

## Eval metrics that would prove it works

- Unsupported-claim rate in edit plans
- Source-span entailment accuracy
- Compile/type/test pass rates
- Semantic regression after apparently successful tests
- Verifier FN/FP rates
- % claims validated by independent evidence

## Risk if done wrong

Same LLM generate+verify; passing weak tests mistaken for proof.

## Related Documents

- [`56-imperfect-graph-agent-decision-roadmap.md`](56-imperfect-graph-agent-decision-roadmap.md)
- [`57-imperfect-graph-failure-modes.md`](57-imperfect-graph-failure-modes.md)
- [`58-imperfect-graph-research-evidence-map.md`](58-imperfect-graph-research-evidence-map.md)
