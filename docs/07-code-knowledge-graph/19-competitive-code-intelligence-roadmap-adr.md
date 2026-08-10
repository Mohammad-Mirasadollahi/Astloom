---
doc_id: as.doc.codegraph.competitive-intelligence-roadmap-adr
title: 19 - Competitive Code Intelligence Roadmap ADR
doc_type: adr
status: active
schema_version: '1.0'
owner: code-graph-lead
summary: Adopts a three-wave roadmap for Astloom code-graph intelligence inspired by CodeGraph
  (surgical explore), code-review-graph (flows/risk/communities), and graphify (edge confidence
  UX + rationale), without switching SoR to SQLite.
tags:
- code-graph
- adr
- mcp
- review
- rag
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/19-competitive-code-intelligence-roadmap-adr.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- docs/07-code-knowledge-graph/09-context-pack-retrieval-and-agent-workflow.md
- docs/07-code-knowledge-graph/13-codesymbol-projection-adr.md
- docs/07-code-knowledge-graph/05-token-optimization-and-model-routing.md
- docs/07-code-knowledge-graph/21-code-intelligence-prior-art-ideas-and-license.md
- docs/07-code-knowledge-graph/22-code-intelligence-enhancements-feature-specification.md
- docs/07-code-knowledge-graph/THIRD_PARTY_NOTICES.md
- backend/services/code-graph-service/docs/phase-7-api-contract.md
external_refs:
- https://github.com/colbymchenry/codegraph
- https://github.com/tirth8205/code-review-graph
- https://github.com/Graphify-Labs/graphify
- https://arxiv.org/abs/2603.27277
- https://github.com/DeusData/codebase-memory-mcp
doc_version: 1.0.1
audience:
- engineer
- architect
primary_entities:
- CodeGraphService
- ExplorePack
- RiskScore
- ExecutionFlow
- ROUTES_TO
- TESTED_BY
relations_declared:
- type: constrains
  target: backend/services/code-graph-service/
- type: complements
  target: docs/07-code-knowledge-graph/09-context-pack-retrieval-and-agent-workflow.md
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 19 - Competitive Code Intelligence Roadmap ADR


## Purpose

Adopts a three-wave roadmap for Astloom code-graph intelligence inspired by CodeGraph (surgical explore), code-review-graph (flows/risk/communities), and graphify (edge confidence UX + rationale), without switching SoR to SQLite.

## Status

Accepted (2026-07-20).

## Context

Phase 7 already ships polyglot ingest, `CodeSymbol` + `CODE_REL`, call confidence,
hybrid semantic search (pgvector → neighborhood expand), generation context packs,
and MCP tools for search / neighbors / impact.

Competitive open-source code-intelligence tools emphasize product behaviors we
only partially cover:

| Source | Lesson |
| --- | --- |
| [CodeGraph](https://github.com/colbymchenry/codegraph) | One primary explore tool; adaptive output budget / sibling skeletonization; framework routes; file-watch freshness; dynamic-dispatch provenance |
| [code-review-graph](https://github.com/tirth8205/code-review-graph) | Leiden communities; execution flows + criticality; risk-scored change review; `TESTED_BY`; hybrid FTS + embedding via RRF; hub/bridge/surprise |
| [graphify](https://github.com/Graphify-Labs/graphify) | Edge confidence as first-class UX; god nodes / surprising connections / suggested questions; shortest path; rationale nodes; agent skill/hook steering |

Astloom keeps **Neo4j (+ Postgres/pgvector)** as SoR. We adopt algorithms and
agent UX patterns, not local SQLite clones.

### Codebase-Memory (2026) — Wave-adjacent prior art

[Codebase-Memory](https://arxiv.org/abs/2603.27277) shows Tree-Sitter knowledge
graphs exposed via MCP can approach file-exploration answer quality at far lower
token cost when stored in SQLite. Astloom **must not** switch SoR to SQLite.
Instead we adopt the **structural-first tool UX** and combine it with existing
explore / hybrid RAG (**hybrid escalate**) for best quality. Normative pack:
`44`–`47` in this folder. Clean-room only — see `21`.

## Decision

### Wave 1 (now) — agent surgical context + change risk

1. **Explore pack** — single query → hybrid seeds (BM25 + semantic + FTS) → call-path
   neighborhood → verbatim/signature bodies under a char budget with sibling
   skeletonization (CodeGraph-inspired).
2. **Framework routes** — emit `ROUTES_TO` edges (FastAPI/Flask/Django/Express
   patterns first) linking URL/method to handler symbols.
3. **`TESTED_BY` edges** — convention-based test↔production links for risk and
   affected-test hints.
4. **Risk-scored change analysis** — map changed files/symbols to flows,
   cross-neighborhood callers, test gaps, and security-name heuristics
   (code-review-graph-inspired weights).
5. **MCP/API surface** — expose `explore` and `detect_changes` (narrow tools;
   prefer explore as the primary agent path). Persist confidence on every edge
   view returned to agents (graphify-style transparency).

### Wave 2 (shipped) — architecture intelligence

6. Community detection via **free scikit-network Leiden** (BSD) with Louvain
   fallback (no Neo4j GDS commercial Leiden, no GPL igraph) over weighted
   `CODE_REL` kinds — details in docs `27`–`29`.
7. Execution-flow tracing + criticality hints in detect_changes / explore packs.
8. Hub / approx-betweenness bridge / knowledge-gap / surprise / suggested-question
   reports via `architecture_overview`.
9. Hybrid **BM25** + semantic + store FTS with **RRF** (`search:hybrid`);
   BGE embeddings by default; turbovec remains Stage-2 optional only (`27`–`31`).
10. Shortest symbol path (`graph/path`).

### Wave 3 (shipped core; watcher daemon deferred) — product polish

11. Session **pending-sync / freshness** banners (MCP `freshness`, explore/
    detect_changes payloads) — full filesystem watcher daemon still deferred.
12. Dynamic-dispatch synthesis with `metadata.provenance=dynamic_dispatch` on
    heuristic `CALLS`.
13. Agent skill/rules that prefer graph explore before wide Read/Grep.
14. Rationale / `# WHY:` comment nodes (`SymbolKind.RATIONALE`) linked via
    `DOCUMENTED_BY`; optional SQL-schema ingest still deferred.
15. Multimodal docs/PDF (graphify) only if product scope expands beyond code.

### v1 freshness marketing freeze (backlog `34` Phase B)

**Decision (2026-07-21):** Astloom v1 markets **explicit ingest + session
pending-sync only**. Do not claim “always live”, “continuous index”, or
save-triggered indexing. A filesystem watcher sidecar remains an optional
ops follow-up (not a v1 launch blocker).

### Explicit non-goals

- Replacing Neo4j with per-project SQLite as the durable graph store.
- Vendoring DeusData Codebase-Memory binaries or copying their source.
- Shipping 30+ MCP tools by default (follow CodeGraph: one strong primary tool;
  Codebase-Memory hybrid adds a few narrow structural tools only).
- Claiming impact “recall 1.0” from graph-derived circular ground truth.
- Marketing Codebase-Memory’s published 83% / 10× figures as Astloom metrics
  without an Astloom-owned evaluation.

## Consequences

- New `rel_type` values `ROUTES_TO` and `TESTED_BY` on `CODE_REL` (logical
  vocabulary; no projection ADR change).
- Optional `SymbolKind.ROUTE` for synthetic route nodes.
- Contract and usage-profile updates for explore / detect_changes.
- Evaluation of risk/explore must use independent signals (e.g. git co-change),
  not only graph self-consistency.

## Wave 1 acceptance (minimal)

- Unit tests cover route extraction, test-link heuristics, risk scoring,
  explore budget/skeletonization.
- HTTP + MCP can return an explore pack and a change-risk report for an
  in-memory or Neo4j-backed project scope.
- Existing Phase 7 ingest/search/generation paths remain green.

## Related

- Context packs: `09-context-pack-retrieval-and-agent-workflow.md`
- Projection: `13-codesymbol-projection-adr.md`
- Prior art + MIT compliance: `21-code-intelligence-prior-art-ideas-and-license.md`, `THIRD_PARTY_NOTICES.md`
- Feature / HLD / LLD / contracts / risks: `22`–`26` in this folder
- Codebase-Memory Neo4j hybrid: `44`–`47` in this folder
- Implementation: `backend/services/code-graph-service/src/code_graph_service/domain/`
  (`framework_routes`, `test_links`, `flows`, `risk`, `explore`, `impact`, `http_calls`)
