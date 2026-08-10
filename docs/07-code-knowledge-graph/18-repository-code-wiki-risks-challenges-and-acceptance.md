---
doc_id: as.doc.ckg.repository-code-wiki-risks
title: 18 - Repository Code Wiki Risks Challenges And Acceptance
doc_type: gap
status: draft
schema_version: '1.0'
owner: platform-product
summary: Risks, mitigations, acceptance gates, and open gaps for Repository Code Wiki (documentation
  phase; implementation follow-on).
tags:
- repository-code-wiki
- risks
- acceptance
- security
- cost
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/18-repository-code-wiki-risks-challenges-and-acceptance.md
lifecycle_lane: future
concern_lane: problem
audience_lane:
- platform-engineering
- security
- product
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.ckg.repository-code-wiki-feature-spec
- as.doc.ckg.repository-code-wiki-contracts
- as.doc.ckg.repository-code-wiki-hld
doc_version: 1.0.1
audience:
- engineer
- architect
- product
- security
primary_entities:
- WikiGenerationJob
- WikiPage
relations_declared:
- type: depends_on
  target: as.doc.ckg.repository-code-wiki-feature-spec
- type: complements
  target: docs/10-gap-analysis/00-index.md
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 18 - Repository Code Wiki Risks Challenges And Acceptance

## Purpose

This document records risks, mitigations, acceptance gates, and remaining open gaps for Repository Code Wiki. Feature behavior is owned by the feature specification; this file owns verification and residual risk.

## Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Unbounded LLM cost on monorepos | Budget blowouts, noisy pages | Hard token/wall-clock budgets; require `focus`/`include` above module threshold; per-tenant concurrency caps |
| Hallucinated APIs in wiki prose | Misleading agents/humans | Graph-grounded prompts; forbid inventing symbols; low-confidence markers; link to living symbol docs |
| Secret leakage into pages | Security incident | Mandatory exclude patterns; secret scanners on draft before publish; redact on detect |
| Invalid Mermaid breaking viewers | Broken UX | Validate before persist; placeholder + finding on failure |
| Dual truth vs symbol living docs | Conflicting explanations | Wiki links down to symbols; incremental refresh on dirty modules; stale badges |
| Confusion with external CodeWiki | Wrong ops expectations / license risk | Docs state inspiration only; no CLI shell-out; Astloom contracts and LiteLLM only |
| Publish without review on regulated projects | Policy violation | `publish_requires_review` flag; RBAC on publish |
| Stale published wiki after large refactors | Agents plan on obsolete architecture | Stale detection vs HEAD; MCP `stale` flag; deferred update jobs |
| Prompt injection via `instructions` or poisoned comments | Agent follows attacker text | Bound instructions size; approval for config changes; treat code comments as untrusted input |
| Cross-project MCP access | Data leak | Env scope; ignore foreign project ids; Usage Profile gates |
| Docs-sync treating generated wiki as human ADR-quality | Incorrect merge blocks or trust | Explicit `status: generated`; configurable drift severity for wiki paths |

## Challenges

- Preserving architectural context under aggressive token caps without dumping full source.
- Stable `module_key` / `wiki_page_id` across renames and package moves.
- Language matrix parity: wiki quality cannot exceed parser/graph support (`10-language-support-policy.md`).
- Optional HTML viewer export without becoming a second SoT.
- Mapping CodeWikiBench-style quality evaluation into Astloom Live Tests without importing their benchmark harness wholesale.

## Engineering Acceptance Criteria

- [ ] Full generate produces overview + ≥1 module page + ≥1 validated diagram on a seeded fixture repo.
- [ ] Incremental mode regenerates a dirty subset after a single-module change; clean modules keep `wiki_page_id` and `content_hash` when unchanged.
- [ ] All model calls use LiteLLM aliases; unit test fails if a vendor SDK is imported in the wiki package.
- [ ] Mermaid validation failure never publishes invalid fences.
- [ ] MCP tools refuse out-of-scope projects and omit tools when feature flag is off.
- [ ] Published Markdown passes docs-sync frontmatter validation.
- [ ] Job cancel stops further module work and ends in `cancelled`.
- [ ] Observability exposes stage, module counts, and token usage by role.

## Product Acceptance Criteria

- [ ] Project admin can configure patterns/doc_type, run generate, review draft, and publish.
- [ ] Developer can browse overview → module → linked symbol without leaving Astloom admin/docs UI.
- [ ] Coding agent can resolve wiki overview via MCP and fetch one module page on demand.
- [ ] Operator sees stale state when HEAD drifts past policy threshold and can run update.
- [ ] Product copy and docs describe Astloom Repository Code Wiki as platform-native, inspired by [CodeWiki](https://github.com/FSoft-AI4Code/CodeWiki) / [codewiki.google](https://codewiki.google/), not as those products embedded.

## Open Gaps

| ID | Gap | Notes |
| --- | --- | --- |
| RCW-G01 | Final service extraction vs wiki package in `code-graph-service` | HLD default: package first; revisit on scale |
| RCW-G02 | Exact published path under multi-root docs layouts | Default `wiki/`; confirm with docs-sync path conventions |
| RCW-G03 | Semantic search backend for wiki (pgvector vs graph-only) | May reuse existing embedding pipeline |
| RCW-G04 | Human edit merge policy when regenerating a manually edited page | Need conflict policy (preserve / overwrite-with-backup / dual) |
| RCW-G05 | Formal quality rubric / golden repos for Live Tests | Optional alignment with CodeWikiBench ideas |
| RCW-G06 | Feature catalog numbering / marketing name lock | “Repository Code Wiki” vs shorter UI label |

Track implementation follow-ups in `../10-gap-analysis/` when engineering starts.

## Related Documents

- [`14-repository-code-wiki-feature-specification.md`](14-repository-code-wiki-feature-specification.md) — requirements.
- [`15-repository-code-wiki-high-level-design.md`](15-repository-code-wiki-high-level-design.md) — architecture.
- [`17-repository-code-wiki-data-contracts-and-events.md`](17-repository-code-wiki-data-contracts-and-events.md) — contracts.
- [`../10-gap-analysis/00-index.md`](../10-gap-analysis/00-index.md) — gap process.
