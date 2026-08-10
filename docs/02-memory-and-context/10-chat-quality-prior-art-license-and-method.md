---
doc_id: as.doc.memory.chat-quality-prior-art-license
title: 10 - Chat Quality Prior Art License And Method
doc_type: standard
status: draft
schema_version: '1.0'
owner: platform-architecture
summary: License-verified open-source chat/RAG prior-art sources, study method, clean-room
  policy, and index of quality idea catalogs for improving Astloom Chat accuracy.
tags:
- chat
- rag
- prior-art
- license
- quality
- compliance
phase: 02-memory-and-context
canonical_path: docs/02-memory-and-context/10-chat-quality-prior-art-license-and-method.md
lifecycle_lane: future
concern_lane: standard
audience_lane:
- platform-engineering
- security
- product
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- docs/02-memory-and-context/09-chat-qa-rag-incremental-documentation.md
- docs/02-memory-and-context/11-chat-quality-retrieval-ranking-and-context-packing.md
- docs/02-memory-and-context/12-chat-quality-grounding-citations-refusal.md
- docs/02-memory-and-context/13-chat-quality-query-rewrite-memory-feedback.md
external_refs:
- https://github.com/infiniflow/ragflow
- https://github.com/Mintplex-Labs/anything-llm
- https://github.com/danny-avila/LibreChat
- https://github.com/Cinnamon/kotaemon
- https://github.com/microsoft/graphrag
doc_version: 1.0.1
audience:
- engineer
- architect
- product
- security
primary_entities:
- PriorArtIdea
- LicenseObligation
- ChatQualityLever
relations_declared:
- type: complements
  target: docs/02-memory-and-context/09-chat-qa-rag-incremental-documentation.md
- type: complements
  target: docs/07-code-knowledge-graph/20-repository-code-wiki-prior-art-ideas-and-license.md
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 10 - Chat Quality Prior Art License And Method

## Purpose

This document defines **how** Astloom studies open-source Chat/RAG systems to raise chat answer quality and accuracy, and states **normative license rules**. Sibling catalogs extract transferable ideas by theme:

| Doc | Theme |
| --- | --- |
| [11 - Retrieval, Ranking, Context Packing](./11-chat-quality-retrieval-ranking-and-context-packing.md) | Hybrid search, rerank, RAPTOR, GraphRAG modes, thresholds, pins |
| [12 - Grounding, Citations, Refusal](./12-chat-quality-grounding-citations-refusal.md) | Evidence, citations, empty/query refusal, low-relevance warnings |
| [13 - Query Rewrite, Memory, Feedback](./13-chat-quality-query-rewrite-memory-feedback.md) | Question rewrite, keywords, history, chunk feedback, branching |

Product behavior for Astloom Chat write-back and contradiction UX remains in [09 - Chat Q&A RAG Incremental Documentation](./09-chat-qa-rag-incremental-documentation.md).

This is not legal advice. Re-verify upstream `LICENSE` files before any code copy or redistribution.

## Study Method

1. Select projects with explicit OSS licenses suitable for idea transfer (prefer Apache-2.0 / MIT).
2. Shallow-clone for local read-only analysis (workspace study trees must not be committed as Astloom product source).
3. Read **backend** paths (retrieval, chat orchestration, ranking, citation, feedback) — not marketing README claims alone.
4. Record ideas with: source project, mechanism location, quality benefit, Adopt/Adapt/Avoid, clean-room notes.
5. Prefer re-implementation on Astloom ports (pgvector, Neo4j code graph, LiteLLM, memory-service, MCP) over vendoring upstream runtimes.

## License Snapshot (verified 2026-07-22)

Local clones inspected under an ephemeral study directory (not part of Astloom git product tree).

| Source | Role | License file | Safe use for Astloom |
| --- | --- | --- | --- |
| [infiniflow/ragflow](https://github.com/infiniflow/ragflow) | Enterprise RAG + dialog chat | **Apache-2.0** (`LICENSE`) | Ideas freely. Code copy only under Apache-2.0 NOTICE/attribution. Prefer clean-room |
| [Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm) | Workspace chat + RAG + agents | **MIT** (`LICENSE`, Mintplex Labs Inc.) | Ideas freely. Code copy only under MIT notice. Prefer clean-room |
| [danny-avila/LibreChat](https://github.com/danny-avila/LibreChat) | Multi-provider chat UI/API, agents, MCP | **MIT** root `LICENSE` (Copyright 2026 LibreChat). Note: `package.json` also lists `"license": "ISC"` — treat root `LICENSE` as authoritative for this study; re-check before vendoring | Ideas freely under MIT terms if LICENSE prevails; confirm with counsel if packaging |
| [Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon) | RAG QA + citations + rerank pipelines | **Apache-2.0** (`LICENSE.txt`) | Ideas freely. Prefer clean-room |
| [microsoft/graphrag](https://github.com/microsoft/graphrag) | Graph-based RAG query modes | **MIT** (`LICENSE`, Microsoft Corporation) | Ideas freely. Prefer clean-room on Astloom Neo4j + retrieval stack |

### Explicitly not used as implementation sources in this pack

| Source | Why deferred / caution |
| --- | --- |
| Khoj (AGPL-3.0) | Strong copyleft; ideas may be noted later with counsel, not default Adopt path |
| Dify | Valuable architecture ideas (sandbox, SSRF proxy, node failure policy, loop limits) but license is a **modified Apache** with multi-tenant / commercial / branding constraints — **ideas only**, not treat as standard Apache-2.0 |
| Open WebUI | Valuable RBAC / extension / offline patterns; license has **branding history** — re-read `LICENSE` + history before any copy; prefer clean-room ideas |
| LobeHub / LobeChat | Custom **Community License**; commercial derivative use often needs separate grant — study only |
| Flowise | Core often Apache-2.0 but **enterprise/commercial paths excluded** — never vendor `enterprise/**` without counsel |
| LiteLLM / Langfuse | **Core MIT** vs separate `enterprise/` / `ee/` trees — Astloom may use core patterns via existing LiteLLM gateway ADR; exclude enterprise paths |
| Phoenix (observability) | Elastic License 2.0-class restrictions for some hosted uses — prefer OTel + existing stack |
| Proprietary chat products | Ideas/UX only if publicly described; no scraping or reverse engineering |

## License Risk Tiers (normative)

| Tier | Licenses (examples) | Astloom default |
| --- | --- | --- |
| Low-risk direct use | MIT, BSD-2/3, ISC, Apache-2.0 (standard) | Ideas + optional dependency after SBOM; keep NOTICE/copyright |
| Manual review | AGPL/network copyleft, LGPL/MPL (linking), ELv2, BSL, Community, modified Apache, multi-license repos | Ideas only until counsel + ADR |
| Path-excluded | Any tree under `enterprise/`, `ee/`, `commercial/` | Do not import |

CI for any future vendoring **must**: build SBOM (SPDX or CycloneDX), fail on UNKNOWN/CUSTOM licenses, detect enterprise path imports, lock versions, and record model/dataset/prompt package licenses separately from code licenses.

## Security Patterns To Adapt (ideas only)

From Dify / Open WebUI-class architectures (clean-room; do not copy code):

| Idea | Tag | Astloom use |
| --- | --- | --- |
| Default-deny sandbox (no net/fs) for untrusted tool code | Adapt | If chat ever runs user code/tools |
| SSRF proxy for agent-controlled URLs | Adapt | Any web-fetch tool in chat |
| Plugin process isolation | Adapt | MCP/tool host boundary |
| Per-tool permission + admin-controlled functions | Adopt | Usage Profile allow-lists |
| Offline / private mode | Adopt | Aligns with no-cloud-exfiltration |
| Output size limits + loop limits | Adopt | Chat agent loop guards (doc 13) |

## Clean-Room Policy (normative)

1. **Default:** inspire and re-implement. Do **not** add these repos as Astloom runtime dependencies unless an ADR accepts vendoring + SBOM.
2. **Do not** paste substantial upstream source into Astloom trees.
3. **Do not** copy UI assets, trademarks, or brand copy.
4. When documenting mechanisms, name the upstream project and license; describe behavior in Astloom vocabulary.
5. Apache-2.0 NOTICE obligations apply only if Astloom redistributes Apache-licensed code (or substantial excerpts), not for independent re-implementation of ideas.
6. Keep study clones out of product release artifacts and out of committed source unless explicitly vendored under policy.

## Idea Tag Legend

Used in sibling catalogs:

- **Adopt** — map into Astloom chat quality specs / implementation backlog.
- **Adapt** — keep intent; reshape to Astloom boundaries (LiteLLM-only, project isolation, code-as-authority).
- **Avoid** — conflicts with Astloom law or product boundary.

## Quality Lever Map (overview)

| Lever | Primary prior art | Astloom fit |
| --- | --- | --- |
| Hybrid lexical + dense retrieval | RAGFlow `Dealer.search`, OpenSearch hybrid pipeline | Already partial in code-graph hybrid; extend for chat doc RAG |
| Cross-encoder / LLM rerank | RAGFlow rerank models; kotaemon Cohere/Voyage/TEI/LLM-Trulens | Adapt via LiteLLM / local rerank profile |
| Hierarchical summaries (RAPTOR-like) | RAGFlow RAPTOR tree | Adapt for large doc sets / wiki; not for every symbol |
| Local / global / drift graph query | GraphRAG structured_search | Adapt onto Neo4j communities + living docs |
| Similarity threshold + query refusal | AnythingLLM `chatMode=query` | Adopt for grounded chat mode |
| Pinned / forced context | AnythingLLM pinned docs | Adapt as explicit operator “must include” evidence |
| Post-hoc citation insertion | RAGFlow `insert_citations` | Adapt; align with contradiction Stage-1/2 |
| Empty-knowledge refusal | RAGFlow `empty_response`; AnythingLLM query refusal | Adopt |
| Low relevance warning | kotaemon `CONTEXT_RELEVANT_WARNING_SCORE` | Adopt beside contradiction banner |
| Question rewrite / decompose | kotaemon rewrite pipelines; RAGFlow `full_question` | Adapt |
| Keyword expansion for recall | RAGFlow `keyword_extraction` | Adapt |
| Chunk feedback → rank feature | RAGFlow `chunk_feedback_service` | Adapt carefully (abuse / gaming) |
| Conversation branching | LibreChat message trees | Adapt for explore-alternate-answer UX |
| Token-budgeted context packing | GraphRAG local mixed_context; RAGFlow `message_fit_in` | Adopt |
| Layout-aware ingest / TOC parent chunks | RAGFlow deepdoc + `mom_id` | Adapt for doc KB quality |
| Sufficiency / agentic retrieve loops | RAGFlow advanced_rag harness | Adapt with hard caps |
| Claims on graph entities | GraphRAG covariates | Adapt onto Neo4j symbols |

## Highest-ROI Adopt Backlog (for Astloom Chat)

Ordered for implementation planning (clean-room). Detail IDs live in docs 11–13.

| Priority | Items | Why |
| --- | --- | --- |
| P0 | R-01/R-03/R-19/R-20, R-24/G-01/G-03, R-31/R-33, G-30, Q-01/Q-04, skill eligibility, ChatTurnReceipt | Hybrid+gates, grounded refusal, citation/context split+backfill, rewrite, tool filter, durable write-back proof |
| P1 | R-07/R-34, R-36, G-23/G-27, Q-13/Q-14, R-40/R-41, loop guards, HITL non-blocking | Rerank, ingest questions, citation repair/caps, feedback, budgets, agent safety |
| P2 | R-28/G-28/G-29, R-14–R-16, Q-27/Q-29/Q-31, R-26, sandbox/SSRF | Sufficiency/abstain, graph modes, fork/tools, layout ingest, tool sandbox |

Deep analysis provenance (ephemeral study clones under `/tmp`, not product dependencies): RAGFlow (Apache-2.0), AnythingLLM (MIT), LibreChat (MIT), kotaemon (Apache-2.0), Microsoft GraphRAG (MIT). Re-verify LICENSE files before any future code copy.

## Related Documents

| Document | Relationship |
| --- | --- |
| [09 - Chat Q&A RAG Incremental Documentation](./09-chat-qa-rag-incremental-documentation.md) | Target product behavior |
| [07 - Autonomous Question Discovery And FAQ Memory](./07-autonomous-question-discovery-and-faq-memory.md) | FAQ promotion loop |
| [20 - Repository Code Wiki Prior Art](../07-code-knowledge-graph/20-repository-code-wiki-prior-art-ideas-and-license.md) | Sibling prior-art style |
| [11 / 12 / 13](.) | Detailed idea catalogs |
