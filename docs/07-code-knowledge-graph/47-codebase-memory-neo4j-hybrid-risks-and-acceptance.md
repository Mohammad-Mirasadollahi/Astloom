---
doc_id: as.doc.ckg.codebase-memory-neo4j-hybrid-risks
title: 47 - Codebase-Memory Neo4j Hybrid Risks And Acceptance
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-architecture
summary: Risks, challenges, and acceptance gates for Codebase-Memory hybrid structural tools
  on Neo4j — including honesty vs paper metrics and deferred watcher policy.
tags:
- code-intelligence
- codebase-memory
- risks
- acceptance
- neo4j
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/47-codebase-memory-neo4j-hybrid-risks-and-acceptance.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- security
- product
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.ckg.codebase-memory-neo4j-hybrid-feature-spec
- as.doc.ckg.codebase-memory-neo4j-hybrid-hld
- as.doc.ckg.codebase-memory-neo4j-hybrid-lld
- as.doc.ckg.code-intel-risks
- docs/07-code-knowledge-graph/33-production-retrieval-live-test-gates.md
doc_version: 1.0.1
audience:
- engineer
- architect
- product
- security
primary_entities:
- DirectedImpactReport
- HttpCallEdge
relations_declared:
- type: depends_on
  target: as.doc.ckg.codebase-memory-neo4j-hybrid-feature-spec
- type: complements
  target: as.doc.ckg.code-intel-risks
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 47 - Codebase-Memory Neo4j Hybrid Risks And Acceptance

## Purpose

Capture risks and acceptance gates for the Codebase-Memory hybrid pack so
engineering does not over-claim paper results or ship dual SoR.

## Risk register

| ID | Risk | Mitigation |
| --- | --- | --- |
| R1 | Agents treat impact as complete blast radius | Document confidence filters; escalate hint; no “recall 1.0” claims |
| R2 | HTTP_CALLS false positives flood graph | Cap confidence; prefer exact path match to ROUTES_TO; unit fixtures |
| R3 | Tool sprawl hurts MCP discoverability | Few new tools; keep explore primary for semantic Q |
| R4 | Stale graph after local edits | Freshness banner on structural payloads; explicit sync |
| R5 | License / IP from DeusData binary | Ideas-only clean-room; no vendoring |
| R6 | Marketing paper 83% / 10× as ours | Separate eval; cite prior art only |

## Acceptance gates

1. Unit: callers, directed impact, community, HTTP_CALLS extractors green.
2. MCP profile lists new tools; dispatch maps_to registered.
3. Docs `44`–`47` indexed; LLD progress table matches shipped code.
4. No SQLite graph SoR path introduced.
5. Live Neo4j (optional release gate): callers/impact on fixture project — `live` marker.

## Known limits

- Dynamic dispatch and string-built URLs remain partial.
- Community membership is recomputed (not durable node property) unless later persisted.
- Watcher daemon remains deferred (ADR 19 v1 freshness freeze).

## Related Documents

- Feature [`44`](44-codebase-memory-neo4j-hybrid-feature-specification.md)
- HLD [`45`](45-codebase-memory-neo4j-hybrid-high-level-design.md)
- LLD [`46`](46-codebase-memory-neo4j-hybrid-low-level-design.md)
- Live gates [`33`](33-production-retrieval-live-test-gates.md)
