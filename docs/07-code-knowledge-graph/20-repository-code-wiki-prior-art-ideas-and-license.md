---
doc_id: as.doc.ckg.repository-code-wiki-prior-art-license
title: 20 - Repository Code Wiki Prior Art Ideas And License
doc_type: standard
status: draft
schema_version: '1.0'
owner: platform-architecture
summary: Transferable product and engineering ideas from CodeWiki / Google Code Wiki for Astloom
  improvement, plus mandatory license and IP compliance rules.
tags:
- repository-code-wiki
- prior-art
- license
- mit
- compliance
- inspiration
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/20-repository-code-wiki-prior-art-ideas-and-license.md
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
- as.doc.ckg.repository-code-wiki-feature-spec
- as.doc.ckg.repository-code-wiki-hld
- as.doc.ckg.repository-code-wiki-risks
- as.doc.ckg.wiki-and-graph-composed-retrieval
external_refs:
- https://github.com/FSoft-AI4Code/CodeWiki
- https://codewiki.google/
- https://arxiv.org/abs/2510.24428
- https://opensource.org/licenses/MIT
doc_version: 1.0.1
audience:
- engineer
- architect
- product
- security
primary_entities:
- RepositoryCodeWiki
- PriorArtIdea
- LicenseObligation
relations_declared:
- type: complements
  target: as.doc.ckg.repository-code-wiki-feature-spec
- type: complements
  target: as.doc.ckg.repository-code-wiki-risks
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 20 - Repository Code Wiki Prior Art Ideas And License

## Purpose

This document lists **ideas** Astloom may adopt to improve Repository Code Wiki and related wedge capabilities, drawn from public prior art — primarily open-source [CodeWiki](https://github.com/FSoft-AI4Code/CodeWiki) (FSoft-AI4Code) and the product surface of [Google Code Wiki](https://codewiki.google/). It also states **normative license and IP rules** so engineering never ships non-compliant copies.

This is not legal advice. Before vendoring third-party code or redistributing binaries that include it, have counsel confirm obligations against the then-current upstream license files.

## License Snapshot (as of 2026-07-20)

| Source | What it is | License / IP posture | Safe use for Astloom |
| --- | --- | --- | --- |
| [FSoft-AI4Code/CodeWiki](https://github.com/FSoft-AI4Code/CodeWiki) | Open-source framework + CLI | Declared **MIT** in `pyproject.toml` and README badge (`License :: OSI Approved :: MIT License`). A root `LICENSE` file was **not** present in the default branch at check time — treat metadata as intent; re-verify before any code copy | **Ideas freely.** Code copy only under MIT terms (copyright notice + permission notice in distributions). Prefer re-implementation on Astloom graph/LiteLLM |
| [arXiv:2510.24428](https://arxiv.org/abs/2510.24428) | Research paper (methods, eval) | Academic publication; cite when claiming results or copying substantial text | Implement methods independently; **cite** in papers/docs if describing their eval; do not paste paper prose into product UI |
| [codewiki.google](https://codewiki.google/) | Google product / service | Proprietary Google IP; ToS apply to the service | **Ideas and UX patterns only.** No scraping, no reverse-engineering binaries, no copying UI assets/copy, no depending on Google’s service as a runtime dependency |
| CodeWikiBench (referenced by CodeWiki) | Benchmark for repo-doc quality | Confirm license before importing harness/data | Ideas for **our** Live Test rubrics OK; import datasets/code only after license check |

### MIT obligations if we ever copy CodeWiki code

If Astloom includes unmodified or modified CodeWiki source (or substantial verbatim excerpts):

1. Keep the copyright notice and MIT permission notice in the redistributed form required by MIT.
2. Record the dependency in third-party notices / SBOM.
3. Do **not** imply FSoft or Google endorsement.
4. Prefer a clean-room re-implementation that uses Astloom’s Code-Knowledge Graph, docs-sync, and LiteLLM ports instead of vendoring the CLI.

**Default Astloom policy:** inspire and re-implement; do **not** add `FSoft-AI4Code/CodeWiki` as a runtime dependency unless an ADR explicitly accepts MIT vendoring and SBOM updates.

## Idea Catalog (transferable)

Each idea is tagged:

- **Adopt** — map into Astloom specs / future implementation.
- **Adapt** — keep the intent; change shape to fit Astloom boundaries.
- **Avoid** — conflicts with Astloom product/law (control-plane, LiteLLM-only, isolation).

### A. Core generation architecture

| ID | Idea | Tag | Astloom use |
| --- | --- | --- | --- |
| I-01 | **Hierarchical decomposition** of large repos into coherent modules before documenting | Adopt | Already in LLD: token thresholds + max depth over graph tree |
| I-02 | **Recursive / multi-agent documentation** (leaf → parent → overview) | Adopt | Wiki workers with bounded concurrency; parent prompts use child summaries only |
| I-03 | **Multi-modal synthesis** (Markdown + architecture / data-flow / sequence diagrams) | Adopt | Mermaid (or AST) + validation gate before publish |
| I-04 | **Dependency / call-aware analysis** before prose generation | Adapt | Prefer Neo4j Code-Knowledge Graph over a parallel tree-sitter-only analyzer; extend language matrix via existing policy |
| I-05 | **Feature-oriented module clustering** + topological order | Adapt | Cluster on graph communities / package boundaries; order dirty-set by deps |
| I-06 | **Separate cluster-model vs main-model vs fallback-model** | Adapt | Express as LiteLLM aliases in `ModelRoutingProfile` (no direct vendor SDKs) |

### B. Operator and cost control

| ID | Idea | Tag | Astloom use |
| --- | --- | --- | --- |
| I-07 | **`--include` replaces defaults; `--exclude` merges** | Adopt | Documented in LLD; implement same semantics for operator familiarity |
| I-08 | **`--focus` modules** for detail vs summary | Adopt | Monorepo safety valve; fail closed when module count exceeds threshold without focus |
| I-09 | **`doc_type` presets** (`api`, `architecture`, `developer`, `user-guide`) | Adopt | Prompt/style packs; admin setting |
| I-10 | **Persistent agent instructions** (include/exclude/focus/doc_type/custom text) | Adapt | Project config + audit; size-cap custom text; treat as prompt-influencing |
| I-11 | **Token budgets** (global / per-module / per-leaf) | Adopt | Hard abort → `partial_success` / `failed` |
| I-12 | **`max_depth` for decomposition** | Adopt | Config key already specified |
| I-13 | **Incremental `--update` / `--compare-to`** | Adopt | Dirty-set vs baseline commit; CI-friendly compare override |

### C. Output and consumption UX

| ID | Idea | Tag | Astloom use |
| --- | --- | --- | --- |
| I-14 | **Stable output tree**: `overview.md`, module pages, `module_tree.json`, `metadata.json` | Adopt | Under project `wiki/`; feed docs-sync |
| I-15 | **Self-documenting dogfood** (“tool documents itself”) | Adapt | Optional Live Test: generate wiki for Astloom sample slice |
| I-16 | **Interactive HTML viewer** (GitHub Pages style) | Adapt | Optional export artifact only; SoT remains Markdown + APIs |
| I-17 | **Browse overview → modules → diagrams** as first-class IA | Adopt | Admin Code Wiki viewer |
| I-18 | **MCP / IDE-driven generation tools** (CodeWiki exposes tools to agents) | Adapt | Astloom MCP: resolve / get-page / search; generation via governed jobs not unconstrained agent writes |
| I-19 | **Google Code Wiki-style “ask the wiki” Q&A over generated docs** | Adapt | Normative composition: [`43-wiki-and-graph-composed-retrieval.md`](43-wiki-and-graph-composed-retrieval.md) (wiki + graph + hybrid docs; Astloom retrieval stack only, not Google) |

### D. Quality and evaluation

| ID | Idea | Tag | Astloom use |
| --- | --- | --- | --- |
| I-20 | **Repository-level doc quality benchmark** (CodeWikiBench concept) | Adapt | Build Astloom golden repos + rubric for Live Tests; do not import bench code/data until license confirmed |
| I-21 | **Mermaid validation before accept** | Adopt | Non-negotiable publish gate |
| I-22 | **Ground prose in real components** (read tools + deps tools in their agent loop) | Adapt | Supply graph excerpts + living symbol docs; forbid inventing symbols |

### E. Explicitly avoid or heavily constrain

| ID | Idea | Tag | Why |
| --- | --- | --- | --- |
| I-23 | Shell out to upstream `codewiki` CLI inside Astloom | Avoid | Breaks LiteLLM-only, audit, project isolation, SBOM clarity |
| I-24 | Subscription mode via Claude Code / Codex CLI as primary path | Avoid (v1) | Out of Astloom gateway boundary unless future ADR |
| I-25 | Global user keychain config (`~/.codewiki`) as SoT | Avoid | Astloom uses project/tenant config and secrets management |
| I-26 | Auto-create git branches / GitHub Pages publish by default | Avoid | Requires explicit operator policy; default off |
| I-27 | Copy Google Code Wiki UI, branding, or service API | Avoid | Proprietary |
| I-28 | Replace symbol-level living docs with wiki-only | Avoid | Wiki complements graph node docs; both stay |

## Mapping To Astloom Improvement Levers

| Lever | Ideas | Expected improvement |
| --- | --- | --- |
| Lower hallucination / better architecture answers | I-01–I-05, I-22 | Agents start from overview + module pages instead of raw tree dumps |
| Lower token cost | I-02, I-08, I-11–I-13 | Hierarchical summaries + incremental dirty-set |
| Faster onboarding (human + agent) | I-14, I-17, I-19 | Clear entry document and navigable module tree |
| Operability | I-07–I-10, I-21 | Predictable filters, styles, validation |
| Measurable quality | I-20 | Live Test gates for wiki freshness and structure |
| Platform fit | Adapt tags + Avoid list | Keeps control-plane, graph SoT, LiteLLM, docs-sync |

## Compliance Checklist (normative)

Before any PR that touches Repository Code Wiki implementation:

- [ ] No Google Code Wiki code, assets, or scraped content.
- [ ] No new dependency on `FSoft-AI4Code/CodeWiki` unless ADR + SBOM + MIT notice approved.
- [ ] If MIT code is copied: copyright and permission notices retained; NOTICE/SBOM updated.
- [ ] Paper methods re-implemented cleanly; citations added where we discuss their eval numbers.
- [ ] Product copy says “inspired by” / “prior art”, not “powered by CodeWiki” or “Google Code Wiki inside”.
- [ ] Secrets excludes and prompt-injection controls remain in force for instructions and code excerpts.

## Related Documents

- [`14-repository-code-wiki-feature-specification.md`](14-repository-code-wiki-feature-specification.md) — product requirements.
- [`15-repository-code-wiki-high-level-design.md`](15-repository-code-wiki-high-level-design.md) — architecture (no CLI shell-out).
- [`18-repository-code-wiki-risks-challenges-and-acceptance.md`](18-repository-code-wiki-risks-challenges-and-acceptance.md) — residual license/confusion risks.
- External: [CodeWiki](https://github.com/FSoft-AI4Code/CodeWiki), [codewiki.google](https://codewiki.google/), [arXiv:2510.24428](https://arxiv.org/abs/2510.24428).
