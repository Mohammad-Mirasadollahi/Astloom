---
doc_id: as.doc.ckg.code-intel-prior-art-license
title: 21 - Code Intelligence Prior Art Ideas And License
doc_type: standard
status: draft
schema_version: '1.0'
owner: platform-architecture
summary: Transferable product and engineering ideas from CodeGraph, code-review-graph,
  graphify, DeusData codebase-memory-mcp, and yamadashy/repomix for Astloom code
  intelligence, plus mandatory MIT license and IP compliance rules (clean-room default).
tags:
- code-intelligence
- prior-art
- license
- mit
- compliance
- codegraph
- graphify
- codebase-memory
- repomix
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/21-code-intelligence-prior-art-ideas-and-license.md
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
- as.doc.codegraph.competitive-intelligence-roadmap-adr
- as.doc.ckg.code-intel-feature-spec
- as.doc.ckg.code-intel-risks
- as.doc.ckg.repository-code-wiki-prior-art-license
- as.doc.ckg.codebase-memory-neo4j-hybrid-feature-spec
- as.doc.ckg.third-party-notices
- as.doc.ckg.codebase-memory-language-breadth-and-speed
- as.doc.ckg.repomix-prior-art-ideas-and-license
- as.doc.ckg.headroom-native-context-compression
external_refs:
- https://github.com/colbymchenry/codegraph
- https://github.com/tirth8205/code-review-graph
- https://github.com/Graphify-Labs/graphify
- https://arxiv.org/abs/2603.27277
- https://github.com/DeusData/codebase-memory-mcp
- https://github.com/yamadashy/repomix
- https://github.com/headroomlabs-ai/headroom
- https://opensource.org/licenses/MIT
- https://www.apache.org/licenses/LICENSE-2.0
doc_version: 1.4.3
audience:
- engineer
- architect
- product
- security
primary_entities:
- CodeIntelligenceEnhancement
- PriorArtIdea
- LicenseObligation
relations_declared:
- type: complements
  target: as.doc.codegraph.competitive-intelligence-roadmap-adr
- type: complements
  target: as.doc.ckg.code-intel-feature-spec
- type: complements
  target: as.doc.ckg.repository-code-wiki-prior-art-license
- type: complements
  target: as.doc.ckg.codebase-memory-neo4j-hybrid-feature-spec
- type: complements
  target: as.doc.ckg.repomix-prior-art-ideas-and-license
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 21 - Code Intelligence Prior Art Ideas And License

## Purpose

This document catalogs **ideas** Astloom may adopt to improve Code-Knowledge Graph agent and review workflows, drawn from public MIT-licensed projects (CodeGraph, code-review-graph, graphify, DeusData codebase-memory-mcp, and yamadashy/repomix). It states **normative license and IP rules** so engineering never ships non-compliant copies.

This is not legal advice. Before vendoring third-party source or redistributing binaries that include it, counsel must confirm obligations against the then-current upstream `LICENSE` files.

Sibling specs: feature (`22`), HLD (`23`), LLD (`24`), contracts (`25`), risks (`26`). Codebase-Memory hybrid: `44`–`47`. Repomix pack ideas: [`53`](53-repomix-prior-art-ideas-and-license.md). Roadmap ADR: `19`. Attribution SSOT: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## License Snapshot (re-verified 2026-07-25)

| Source | Role | License | Copyright (upstream LICENSE) | Safe use |
| --- | --- | --- | --- | --- |
| [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph) | Local code KG + MCP explore for agents | **MIT** (`LICENSE` on `main`) | Copyright (c) 2026 Colby Mchenry | Ideas freely. Code copy only under MIT. Prefer clean-room on Neo4j |
| [tirth8205/code-review-graph](https://github.com/tirth8205/code-review-graph) | Review-oriented graph, blast radius, risk | **MIT** (`LICENSE` on `main`) | Copyright (c) 2026 Tirth Kanani | Ideas freely. Code copy only under MIT. Prefer clean-room |
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | Multi-source KG skill; confidence-tagged edges | **MIT** (`LICENSE` on `v8`) | Copyright (c) 2026 Safi Shamsi | Ideas freely. Code copy only under MIT. Prefer clean-room |
| [Codebase-Memory (arXiv:2603.27277)](https://arxiv.org/abs/2603.27277) / [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Tree-Sitter KG + MCP; SQLite SoR; Hybrid LSP; 15 tools | **MIT** (`LICENSE` on `main`, commit `97ce23f`) | Copyright (c) 2025 DeusData | **Ideas only by default.** Do **not** vendor the C binary or grammars. Clean-room on Neo4j (`44`–`47`). Notices in `THIRD_PARTY_NOTICES.md` |
| [yamadashy/repomix](https://github.com/yamadashy/repomix) | AI-friendly repo pack (XML/MD), token budget, Secretlint, Tree-sitter compress | **MIT** (`LICENSE` on `main`, commit `f096892`) | Copyright 2024 Kazuki Yamada | **Ideas only by default.** Full catalog [`53`](53-repomix-prior-art-ideas-and-license.md). No hosted pack of private trees |
| [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | Context compression before LLM (JSON/logs/RAG); CCR retrieve | **Apache 2.0** (`LICENSE` on `main`, commit `a6d4921`) | Copyright 2025 Headroom Contributors | **Astloom product must use natively** — [`54`](54-headroom-native-context-compression.md). Not IDE toolstack. Clean-room or ADR dependency |

### Upstream notice obligations

The MIT-licensed sources above use the standard MIT grant. The Headroom source uses **Apache License 2.0** (see [`54`](54-headroom-native-context-compression.md) and `THIRD_PARTY_NOTICES`). If Astloom includes unmodified or modified **source** (or substantial verbatim excerpts) from any of them, distributions **must** retain the corresponding upstream notices and satisfy that license’s redistribution rules.

For **MIT** copies, retain at minimum:

1. The copyright notice for that upstream project.
2. The MIT permission notice (including the warranty disclaimer).
3. SBOM / third-party notices entries (see `THIRD_PARTY_NOTICES.md` in this folder).
4. No implication of endorsement by the upstream authors.

For **Apache 2.0** (Headroom), also satisfy Apache §§4(a)–(d) (LICENSE copy, NOTICE, modification marks) when redistributing.

**Default Astloom policy:** inspire and **re-implement** against Astloom ports (Neo4j `CodeSymbol`/`CODE_REL`, LiteLLM, MCP gateway, native compression per `54`). Do **not** add these packages as runtime dependencies unless an ADR explicitly accepts MIT/Apache vendoring and SBOM updates.

### What “ideas” means

| Allowed without copying code | Not allowed without MIT compliance + ADR |
| --- | --- |
| Algorithms described in docs/README (Leiden, risk weights, explore budget) | Pasting upstream TypeScript/Python modules into Astloom |
| UX patterns (single primary MCP tool, stale banners) | Shipping their CLI/MCP binaries inside Astloom |
| Evaluation methodology concepts (token reduction, co-change grading) | Claiming “powered by CodeGraph/CRG/graphify” without affiliation |
| Independent re-implementation of route regex / test naming heuristics | Scraping proprietary hosted products beyond these MIT repos |

## Idea Catalog (transferable)

Tags: **Adopt** (map into Astloom), **Adapt** (intent kept, shape changed), **Avoid** (conflicts with platform law).

### A. Agent surgical context (primarily CodeGraph)

| ID | Idea | Tag | Astloom mapping |
| --- | --- | --- | --- |
| CI-01 | Single primary explore MCP tool vs many narrow tools | Adopt | `astloom_code_graph_explore` preferred; others secondary |
| CI-02 | Adaptive output budget scaled to repo size | Adopt | `explore_budget_for_file_count` + pack builder |
| CI-03 | Sibling / polymorphic skeletonization (signatures vs full bodies) | Adopt | Explore pack `render: signature\|full` |
| CI-04 | Call-path spine kept verbatim | Adopt | `call_path_ids` + `on_spine` |
| CI-05 | Framework-aware HTTP routes → handler edges | Adopt | `ROUTES_TO` + `SymbolKind.ROUTE` |
| CI-06 | Dynamic-dispatch / bridge synthesis with provenance | Adapt | Wave 3; `metadata.provenance` on heuristic `CODE_REL` |
| CI-07 | File watcher + debounce + staleness banner to agents | Adapt | Wave 3; IDE session freshness, not SQLite daemon |
| CI-08 | Affected tests via transitive imports | Adapt | Wave 1–2; start with `TESTED_BY` conventions |
| CI-09 | FTS5 keyword search | Adapt | BM25 + Neo4j Lucene / Postgres FTS + RRF (`27`–`29`) |
| CI-10 | 100% local SQLite SoR | Avoid | Astloom SoR remains Neo4j (+ Postgres/pgvector) |

### B. Review and architecture analytics (primarily code-review-graph)

| ID | Idea | Tag | Astloom mapping |
| --- | --- | --- | --- |
| CI-11 | Leiden communities with weighted edge kinds | Adopt | scikit-network Leiden or Louvain in-process (portability). GDS Community could run Leiden without Enterprise key but is not used for communities — [`32`](32-intentional-fallbacks-and-neo4j-plugin-licensing.md) |
| CI-12 | Auto-split oversized communities (>25% of graph) | Adopt | Post-process after Leiden |
| CI-13 | Execution flows from entry points + BFS on CALLS | Adopt | Domain `flows` + detect_changes |
| CI-14 | Flow criticality weighted score | Adopt | file_spread / external / security / test_gap / depth |
| CI-15 | Change risk score (flows, tests, security, callers, churn) | Adopt | `detect_changes` / `compute_risk_score` |
| CI-16 | `TESTED_BY` edges | Adopt | Convention linker at ingest |
| CI-17 | Hub (degree) and bridge (betweenness) nodes | Adopt | Wave 2; in-process degree + approx betweenness |
| CI-18 | Knowledge gaps (isolated, thin community, untested hotspot) | Adopt | Wave 2 architecture overview |
| CI-19 | Surprise / unexpected coupling scoring | Adapt | Wave 2; pair with edge confidence |
| CI-20 | Hybrid FTS BM25 + embeddings via RRF | Adopt | Shipped — docs `27`–`31` |
| CI-21 | GitHub Action sticky PR risk comment | Adapt | Optional CI job; local-first on runner |
| CI-22 | Circular “recall 1.0” marketing for impact | Avoid | Evaluate with git co-change / human labels |
| CI-23 | Expose 30 MCP tools by default | Avoid | Prefer CI-01 |

### C. Explainability and multi-source map (primarily graphify)

| ID | Idea | Tag | Astloom mapping |
| --- | --- | --- | --- |
| CI-24 | Edge confidence tiers as first-class UX (`EXTRACTED`/`INFERRED`/`AMBIGUOUS`) | Adapt | Map to Astloom `exact`/`probable`/`ambiguous`/`unresolved`; always surface in MCP |
| CI-25 | God nodes (high degree, noise-filtered) | Adopt | Wave 2 overview |
| CI-26 | Surprising connections + suggested questions | Adopt | Wave 2 report / MCP |
| CI-27 | Shortest path between two symbols/concepts | Adopt | Wave 2 query |
| CI-28 | Rationale / `# WHY:` / ADR nodes linked to code | Adapt | Extend `DOCUMENTED_BY` / rationale kind |
| CI-29 | Agent skill/hook that prefers graph query before Read | Adapt | Usage-profile + workspace guidance |
| CI-30 | Docs/PDF/video in same graph | Adapt | Docs/SQL first; PDF/video only if product expands |
| CI-31 | Memory/reflect loop from Q&A outcomes | Adapt | Optional; tie to Astloom memory BC |
| CI-32 | Commit `graph.json` as team SoT | Avoid | Server Neo4j is SoT; exports are artifacts |

### D. Codebase-Memory structural MCP (paper + open MCP)

Language breadth (~158 grammars + Hybrid LSP) and indexing/query speed stack are documented in
[`52-codebase-memory-language-breadth-and-indexing-speed.md`](52-codebase-memory-language-breadth-and-indexing-speed.md).

Upstream snapshot (ideas only; MIT DeusData): indexing (`index_repository`, `list_projects`, `delete_project`, `index_status`), querying (`search_graph`, `trace_path`, `detect_changes`, `query_graph`, `get_graph_schema`, `get_code_snippet`, `get_architecture`, `search_code`, `manage_adr`, `ingest_traces`), plus guidance patterns such as `check_index_coverage` before absence claims.

| ID | Idea | Tag | Astloom mapping |
| --- | --- | --- | --- |
| CI-33 | Typed structural MCP tools before file Grep | Adopt | **Shipped:** `callers` / directed `impact` / `community` / `call_path` + escalate (`44`–`46`) |
| CI-34 | Whole graph in one SQLite file, zero Neo4j | Avoid | Neo4j SoR (ADR `19`); ideas only |
| CI-35 | HTTP client call edges matched to routes | Adapt | **In progress / domain:** `HTTP_CALLS` (+ `ASYNC_CALLS`) on `CODE_REL` |
| CI-36 | Broad Tree-Sitter grammar matrix in one binary | Adapt | Incremental language matrix (`10`); no DeusData binary or vendored grammars |
| CI-37 | Hybrid: structural then escalate when quality needs it | Adopt | **Shipped:** `escalate_hint` + workspace guidance |
| CI-38 | Hybrid LSP type-resolution pass refining CALLS (no LS process) | Adapt | Keep ADR `48`/`49`: real IDE LSP = `ide_semantic` only; durable edges from AST ingest + reconcile — do **not** embed C Hybrid LSP |
| CI-39 | IaC nodes (Dockerfile / K8s / Kustomize) with cross-refs | Adapt | Future deploy/IaC graph lane; not v1 coding wedge |
| CI-40 | Index-coverage check before “absent / dead” claims | Adopt | **Shipped:** `index_coverage` + freshness fail-closed on scored `unused_candidates`; demotes `safe_to_delete` when incomplete |
| CI-41 | ADR CRUD linked into architecture overview | Adapt | Docs-sync + `DOCUMENTED_BY` / rationale (`CI-28`); no parallel ADR store in SQLite |
| CI-42 | Agent-facing openCypher `query_graph` | Avoid | Prefer typed MCP tools; Neo4j Cypher stays service/ops behind ACL |
| CI-43 | Runtime `ingest_traces` to validate HTTP_CALLS | Adapt | Optional live/eval evidence path; not default agent coding loop |
| CI-44 | `FILE_CHANGES_WITH` co-change edges | Adapt | Risk / eval labels; pair with human/git co-change (not circular recall) |
| CI-45 | Layered ignore (hardcoded → `.gitignore` → project ignore) | Adopt | **Shipped:** sync merges `.gitignore` + `.astloomignore` |
| CI-46 | Multi-tier agent routing (narrow scout vs deep worker) | Adapt | Usage-profile + structural-first guidance; avoid exposing 15+ peer tools |
| CI-47 | Per-account coordination daemon + shared watchers | Avoid | Astloom server sync / explicit `sync`; no host-wide CBM daemon |
| CI-48 | Team-shared zstd/SQLite graph artifact as SoT | Avoid | Same as CI-32; Neo4j is SoT; exports are artifacts |
| CI-49 | Compact / budgeted MCP payloads | Adopt | Explore pack + keep impact/callers/community compact by default |
| CI-50 | Cross-repo fleet architecture summary | Adapt | Later multi-project under tenant/workspace scope |
| CI-51 | Snippet-by-qualified-name after search | Adapt | `get_symbol` / `generation_context` / explore budgeted source |
| CI-52 | Indexed-file `search_code` as peer MCP tool | Avoid | Prefer `hybrid_search`; IDE Grep stays local |
| CI-53 | Embedded 3D graph visualization UI | Adapt | Optional viz later; not on critical MCP path |

### E. Repomix AI-friendly packing (see [`53`](53-repomix-prior-art-ideas-and-license.md))

| ID | Idea | Tag | Astloom mapping |
| --- | --- | --- | --- |
| RM-02 / RM-03 | Token counts + token-budget exit | Adopt | **Shipped:** explore `estimated_tokens`; `astloom pack review --token-budget` |
| RM-04 | Token hotspot tree | Adopt | **Shipped:** pack review `hotspots` |
| RM-05 / RM-06 | Layered ignore + secret scan before pack | Adopt | **Shipped:** `.gitignore`/`!`/`.astloomignore`; pack review fail-closed scan |
| RM-07 / RM-08 | Tree-sitter / per-glob compress | Adapt | Explore skeletonization + pack profiles |
| RM-10 / RM-11 | Stdin file list + diffs in pack | Adapt | **Shipped:** `--files` / `--stdin` / `--from-git` / `--include-diff` |
| RM-18 / RM-19 / RM-20 | Whole-repo pack as primary UX; hosted/remote pack; peer Repomix MCP | Avoid | Graph-first; no cloud pack of private trees |

### F. Headroom context compression (see [`54`](54-headroom-native-context-compression.md))

| ID | Idea | Tag | Astloom mapping |
| --- | --- | --- | --- |
| HR-01 / HR-02 | Compress before LiteLLM; content-aware JSON/code/prose | Adopt | **Native in Astloom** MCP gateway + LLM port |
| HR-03 / HR-04 | CCR retrieve + Astloom MCP compress/retrieve/stats | Adopt | Product tools; not `ai-toolstack` |
| HR-05 | In-process library | Adopt | Preferred embed shape |
| HR-06 / HR-08 | External LLM proxy wrap; upstream cross-agent memory | Avoid | LiteLLM-only; Astloom memory BC |

## Mapping To Improvement Levers

| Lever | Ideas | Expected improvement |
| --- | --- | --- |
| Fewer agent tool calls / tokens | CI-01–CI-04, CI-29, CI-33, CI-37, CI-46, CI-49, RM-02–RM-04, RM-07, HR-01–HR-04 | Surgical packs + structural-first + native compress |
| Safer reviews / PRs | CI-13–CI-16, CI-21, CI-40, CI-44, RM-06, RM-11 | Risk-ranked changes + secret-safe packs |
| Architecture literacy | CI-11–CI-12, CI-17–CI-19, CI-25–CI-27, CI-41 | Communities, bridges, ADR-linked overview |
| Trust in edges | CI-06, CI-24, CI-35, CI-38, CI-43 | Provenance + confidence; IDE LSP separate from durable graph |
| Platform fit | Avoid list + Adapt tags | Neo4j SoR, LiteLLM, tenant scope; native compress in Astloom |

## Compliance Checklist (normative)

Before any PR that implements or vendors code-intelligence features:

- [ ] No vendored copy of CodeGraph / code-review-graph / graphify / DeusData codebase-memory-mcp / yamadashy/repomix / headroomlabs-ai/headroom source or binaries unless ADR + SBOM + license notices approved.
- [ ] If MIT or Apache 2.0 code is copied: retain upstream notices; update `THIRD_PARTY_NOTICES.md` (Apache: LICENSE + NOTICE + modification marks).
- [ ] Product copy may say “inspired by” / “prior art”; must not claim affiliation or “powered by” those products.
- [ ] Benchmarks do not claim circular graph-derived “100% recall” or paper 83%/10× figures as Astloom product metrics without our eval.
- [ ] Secrets, tenant isolation, no-cloud-exfiltration, and LiteLLM-only LLM access remain in force (including pack/export and compression paths).
- [ ] Native context compression is an **Astloom product** obligation ([`54`](54-headroom-native-context-compression.md)); IDE helper stacks are not a substitute.
- [ ] Re-verify upstream `LICENSE` files if bumping a vendored commit (DeusData MIT `97ce23f`; Repomix MIT `f096892`; Headroom Apache 2.0 `a6d4921`).

## Related Documents

- [`19-competitive-code-intelligence-roadmap-adr.md`](19-competitive-code-intelligence-roadmap-adr.md)
- [`22-code-intelligence-enhancements-feature-specification.md`](22-code-intelligence-enhancements-feature-specification.md)
- [`44-codebase-memory-neo4j-hybrid-feature-specification.md`](44-codebase-memory-neo4j-hybrid-feature-specification.md)
- [`52-codebase-memory-language-breadth-and-indexing-speed.md`](52-codebase-memory-language-breadth-and-indexing-speed.md)
- [`53-repomix-prior-art-ideas-and-license.md`](53-repomix-prior-art-ideas-and-license.md)
- [`54-headroom-native-context-compression.md`](54-headroom-native-context-compression.md)
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- External: [CodeGraph](https://github.com/colbymchenry/codegraph), [code-review-graph](https://github.com/tirth8205/code-review-graph), [graphify](https://github.com/Graphify-Labs/graphify), [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) (MIT), [repomix](https://github.com/yamadashy/repomix) (MIT), [headroom](https://github.com/headroomlabs-ai/headroom) (Apache 2.0)
