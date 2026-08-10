---
doc_id: as.doc.ckg.code-intel-risks
title: 26 - Code Intelligence Enhancements Risks Challenges And Acceptance
doc_type: gap
status: draft
schema_version: '1.0'
owner: platform-architecture
summary: Records residual risks and acceptance gates for Code Intelligence Enhancements. License
  rules are normative in [`21`](21-code-intelligence-prior-art-ideas-and-license.md).
tags:
- code-intelligence
- risks
- acceptance
- license
- mit
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/26-code-intelligence-enhancements-risks-challenges-and-acceptance.md
lifecycle_lane: current
concern_lane: problem
audience_lane:
- platform-engineering
- security
- product
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.ckg.code-intel-feature-spec
- as.doc.ckg.code-intel-prior-art-license
- as.doc.codegraph.competitive-intelligence-roadmap-adr
doc_version: 1.0.1
audience:
- engineer
- architect
- security
- product
primary_entities:
- ExplorePack
- ChangeRiskReport
- LicenseObligation
relations_declared:
- type: depends_on
  target: as.doc.ckg.code-intel-feature-spec
- type: depends_on
  target: as.doc.ckg.code-intel-prior-art-license
chunk_hints:
  strategy: heading_h2
  max_tokens: 700
  overlap_tokens: 48
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 26 - Code Intelligence Enhancements Risks Challenges And Acceptance

## Purpose

Records residual risks and acceptance gates for Code Intelligence Enhancements.
License rules are normative in [`21`](21-code-intelligence-prior-art-ideas-and-license.md).

## Risk Register

| ID | Risk | Severity | Mitigation |
| --- | --- | --- | --- |
| R-01 | Accidental vendor of MIT source without notices | High | Clean-room default; CI grep for upstream package paths; NOTICE file |
| R-02 | False “powered by CodeGraph/CRG/graphify” marketing | Medium | Copy review; only “inspired by / prior art” |
| R-03 | Explore packs still larger than grep for tiny edits | Medium | Adaptive budget; skeletonization; document when not to use |
| R-04 | Route regex misses DI/dynamic frameworks | Medium | Confidence `unresolved`; expand frameworks iteratively |
| R-05 | TESTED_BY false positives (`contest.py`) | Medium | Segment-aware test path classifier; unit fixtures |
| R-06 | Risk scores over-trust graph (circular eval) | High | Co-change / human labels for published metrics |
| R-07 | Betweenness/Leiden cost on huge monorepos | Medium | Approx algorithms; job async; size caps |
| R-08 | Stale index misleads agents (pre-watcher) | Medium | Wave 3 stale banners; ingest after save hooks |
| R-09 | Ambiguous handlers create noisy ROUTES_TO | Low | Cap fan-out; surface confidence |
| R-10 | License file upstream change | Low | Re-verify LICENSE on any vendoring ADR |

## Challenges

1. **Parity with SQLite-local tools** — Astloom is multi-tenant Neo4j; freshness
   and daemon UX differ. Do not pretend feature parity with desktop CLIs.
2. **Agent tool selection** — Multiple MCP tools invite misuse; keep explore as
   primary in profiles and skills.
3. **Honest benchmarks** — Token “Nx reduction” vs whole-corpus baselines overstates
   value; report agent-baseline and co-change modes.
4. **Language matrix** — Route/test heuristics start on Python/JS; other languages
   need explicit extractors, not silent claims.

## Acceptance Gates

### Wave 1

- [x] Docs `21`–`26` + `THIRD_PARTY_NOTICES.md` with accurate copyright lines.
- [x] Unit/service tests green for routes, TESTED_BY, explore, detect_changes.
- [x] HTTP + MCP expose explore and detect_changes.
- [x] No upstream source trees vendored under `backend/`.
- [x] Product strings do not claim affiliation with prior-art projects.

### Wave 2

- [x] Free Leiden (scikit-network) or Louvain; no GDS/GPL — see [`31`](31-production-retrieval-stack-risks-challenges-and-acceptance.md).
- [x] Hybrid BM25 + semantic + FTS RRF (`search:hybrid` + explore) — docs `27`–`30`.
- [x] Architecture overview API returns hubs/bridges/gaps/surprises (in-process).
- [x] Shortest path API/MCP.

### Wave 3

- [x] Pending-sync / freshness contract + MCP tool (watcher daemon deferred).
- [x] Provenance `dynamic_dispatch` on heuristic CALLS.
- [x] Rationale nodes from `# WHY:` / `NOTE:` / `HACK:` comments.
- [x] Agent skill prefers explore first.
- [ ] License re-check if any vendoring ADR opens.
- [x] Optional filesystem poll sidecar for pending-sync (`watch_pending_sync.py` / `astloom graph watch`) — **batched** (debounce + max-wait); not per-edit; not continuous index.

## Open Gaps

| Gap | Owner | Notes |
| --- | --- | --- |
| Watcher deployment model | platform-ops | Poll sidecar shipped (`graph watch`); v1 still markets explicit ingest + pending-sync |
| Full DI / framework import matrix | code-graph-lead | **Closed for v1 wedge:** FastAPI `Depends` + Nest/TS constructor/`@Inject` CALLS (`di_injection`); package manifests include Cargo/tsconfig/go replace. Exotic DI frameworks remain iterative (R-04). |

## Honesty eval (Phase A — durable)

- [x] Co-change eval harness for explore & change-risk (`tests/.../ckg_eval/`, ADR 19 non-circular labels). Explore packs include `file_path` on symbols/sections.
- [x] Community quality vs co-change scored report (`community-vs-cochange-latest.json`).
- Do **not** publish F1 / community-quality marketing without these harness reports.

## Related Documents

- Feature: [`22`](22-code-intelligence-enhancements-feature-specification.md)
- Production retrieval: [`27`](27-production-retrieval-stack-feature-specification.md)–[`31`](31-production-retrieval-stack-risks-challenges-and-acceptance.md)
- Intentional fallbacks / plugin licensing: [`32`](32-intentional-fallbacks-and-neo4j-plugin-licensing.md)
- License: [`21`](21-code-intelligence-prior-art-ideas-and-license.md)
- Notices: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- Roadmap ADR: [`19`](19-competitive-code-intelligence-roadmap-adr.md)
