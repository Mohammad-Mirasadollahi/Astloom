---
doc_id: as.doc.ckg.repository-code-wiki-contracts
title: 17 - Repository Code Wiki Data Contracts And Events
doc_type: contract
status: draft
schema_version: '1.0'
owner: platform-architecture
summary: This document defines public contracts for Repository Code Wiki jobs, pages, module
  trees, publish results, MCP tools, and events. Algorithms live in the low-level design;
  REST path naming must follow `../14-api-design-and-naming-standards/`.
tags:
- repository-code-wiki
- contracts
- mcp
- events
- api
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/17-repository-code-wiki-data-contracts-and-events.md
lifecycle_lane: future
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.ckg.repository-code-wiki-lld
- as.doc.ckg.repository-code-wiki-feature-spec
- as.doc.ckg.repository-code-wiki-hld
doc_version: 1.0.1
audience:
- engineer
- architect
- agent
primary_entities:
- WikiGenerationJob
- WikiPage
- WikiModuleTree
- WikiPublishResult
relations_declared:
- type: depends_on
  target: as.doc.ckg.repository-code-wiki-lld
- type: complements
  target: docs/14-api-design-and-naming-standards/01-api-design-principles.md
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 17 - Repository Code Wiki Data Contracts And Events

## Purpose

This document defines public contracts for Repository Code Wiki jobs, pages, module trees, publish results, MCP tools, and events. Algorithms live in the low-level design; REST path naming must follow `../14-api-design-and-naming-standards/`.

## Contract Families

Design target package: `backend/packages/code_graph/contracts/wiki` (or `code_wiki` namespace inside code-graph contracts).

| Contract | Role |
| --- | --- |
| `WikiConfig` | Include/exclude/focus, doc_type, depth, token budgets, model profile id, instructions |
| `WikiJobCreateRequest` | mode, config, baseline_commit?, compare_to? |
| `WikiGenerationJob` | Job resource |
| `WikiModuleTree` | Hierarchical modules |
| `WikiPage` | Draft or published page |
| `WikiArtifact` | Diagram / attachment |
| `WikiPublishRequest` | draft job id, review attestation? |
| `WikiPublishResult` | Written paths + validation errors |
| `WikiResolveRequest` | MCP: scope + optional module_key + budgets |
| `WikiResolveBundle` | Overview summary + tree stubs + optional page bodies |
| `WikiSearchHit` | Search result row |

## WikiConfig Sketch

```json
{
  "include": ["**/*.py", "backend/**/*.ts"],
  "exclude": ["tests", "*.test.py"],
  "focus": ["src/core", "src/api"],
  "doc_type": "architecture",
  "max_depth": 2,
  "max_tokens": 32768,
  "max_token_per_module": 36369,
  "max_token_per_leaf_module": 16000,
  "model_profile_id": "mrp_wiki_default",
  "instructions": "Focus on public APIs and include usage examples",
  "publish_requires_review": true
}
```

## WikiGenerationJob Sketch

```json
{
  "job_id": "wikijob_01HZX...",
  "project_id": "prj_123",
  "mode": "full",
  "status": "generating",
  "baseline_commit": "abc123",
  "compare_to": null,
  "head_commit": "def456",
  "config_hash": "sha256:...",
  "progress": {
    "stage": "generating",
    "modules_total": 42,
    "modules_done": 10,
    "modules_failed": 0
  },
  "token_usage": {
    "cluster": 12000,
    "main": 88000,
    "leaf": 210000
  },
  "error_class": null,
  "created_at": "2026-07-20T18:00:00Z",
  "updated_at": "2026-07-20T18:05:00Z"
}
```

Statuses: `queued` \| `planning` \| `generating` \| `synthesizing` \| `draft_ready` \| `publishing` \| `published` \| `partial_success` \| `failed` \| `cancelled`.

## WikiPage Sketch

```json
{
  "wiki_page_id": "wikipg_01HZX...",
  "project_id": "prj_123",
  "module_key": "src/api",
  "title": "src/api",
  "doc_id": "ac.wiki.demo.src-api",
  "lifecycle": "draft",
  "body_markdown": "# src/api\n\n...",
  "content_hash": "sha256:...",
  "linked_symbols": ["src/api/handlers.py::create_job"],
  "artifacts": [
    {
      "artifact_id": "wikiart_01HZX...",
      "kind": "architecture",
      "content_hash": "sha256:...",
      "validation": "passed"
    }
  ],
  "flags": {
    "diagram_validation_failed": false,
    "degraded_graph": false,
    "confidence": "medium"
  },
  "baseline_commit": "abc123"
}
```

`lifecycle`: `draft` \| `published` \| `retired`.

## HTTP API (illustrative)

Follow API naming standards for final paths; illustrative resource verbs:

| Operation | Intent |
| --- | --- |
| `POST .../code-wiki/jobs` | Create job |
| `GET .../code-wiki/jobs/{job_id}` | Get job |
| `POST .../code-wiki/jobs/{job_id}/cancel` | Cancel |
| `POST .../code-wiki/jobs/{job_id}/publish` | Publish draft |
| `GET .../code-wiki/tree` | Published (or draft=) module tree |
| `GET .../code-wiki/pages/{module_key}` | Get page by module key |
| `GET .../code-wiki/search?q=` | Keyword/semantic hybrid search over published wiki |

Idempotency: `Idempotency-Key` header on create job; server key also derived from `(project_id, mode, baseline/compare, config_hash)`.

## MCP Tools

| Tool | Input | Output |
| --- | --- | --- |
| `astloom_wiki_resolve` | project scope (from env), optional `module_key`, token budget | `WikiResolveBundle` |
| `astloom_wiki_get_page` | `module_key` or `wiki_page_id` | `WikiPage` (published) |
| `astloom_wiki_search` | `q`, `limit` | `WikiSearchHit[]` |

Tools appear only when Usage Profile allow-lists them and `code_wiki.enabled` is true. Out-of-scope project ids → tool error; do not leak existence across tenants.

### Resolve Bundle Sketch

```json
{
  "bundle_id": "wikibnd_01HZX...",
  "project_id": "prj_123",
  "published_baseline_commit": "abc123",
  "stale": false,
  "overview_excerpt": "...",
  "tree_stub": [{"module_key": "src/api", "title": "src/api"}],
  "pages": [],
  "token_estimate": 900,
  "audit_record_id": "aud_..."
}
```

Default resolve returns overview excerpt + tree stub only; page bodies require get-page or explicit `include_module_keys`.

## Events

Envelope follows platform event standards (correlation id, tenant, project, schema version).

| Event | When | Key payload |
| --- | --- | --- |
| `WikiGenerationJobStarted` | Job enters planning | job_id, mode, baseline_commit |
| `WikiGenerationJobCompleted` | Terminal non-cancel | job_id, status, token_usage, failed_modules |
| `WikiGenerationJobCancelled` | Cancelled | job_id |
| `WikiPublished` | Publish success | job_id, page_count, published_at |
| `WikiPageStale` | Freshness policy breach | module_key?, head_commit, published_baseline |
| `WikiDiagramValidationFailed` | Artifact rejected | wiki_page_id, artifact_kind, error |

Consumers: Activity/WorkLog, docs-sync reindex, optional Issue creation on repeated failures, admin notifications.

## Versioning And Compatibility

- Contract schema version in package `schema_version`; breaking field renames require new major.
- Published `doc_id` values remain stable across wiki feature upgrades.
- MCP tool names are additive; deprecate with Usage Profile notes, do not reuse names for different semantics.

## Related Documents

- [`16-repository-code-wiki-low-level-design.md`](16-repository-code-wiki-low-level-design.md) — algorithms and layout.
- [`14-repository-code-wiki-feature-specification.md`](14-repository-code-wiki-feature-specification.md) — required behaviors.
- [`../14-api-design-and-naming-standards/00-index.md`](../14-api-design-and-naming-standards/00-index.md) — API grammar.
