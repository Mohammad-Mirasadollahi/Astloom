---
doc_id: as.doc.ckg.documentation-catalog-and-lane-cache
title: Documentation Catalog and Lane Cache
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Normative agent-facing documentation catalog—observed tag/lane vocabularies from
  each software's scanned frontmatter (not a global hardcoded enum), plus a cached index so
  coding agents can narrow which Markdown to read without inventing DOCUMENTED_BY edges. Covers
  CLI docs-catalog, MCP astloom_docs_catalog, configurable roots, cache path, filters, refresh
  rules, and how astloom sync consumes the catalog to order Phase 2 evidence linking (resolve-only
  edges).
tags:
- standard
- ckg
- documentation
- catalog
- tags
- lanes
- cache
- mcp
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/42-documentation-catalog-and-lane-cache.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/packages/astloom_cli/docs_catalog.py::build_docs_catalog
- backend/packages/astloom_cli/docs_catalog.py::get_docs_catalog
- backend/packages/astloom_cli/docs_catalog.py::filter_docs_catalog
- backend/packages/astloom_cli/commands/docs_catalog.py::cmd_docs_catalog
- backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs
- backend/services/mcp-gateway-service/src/mcp_gateway_service/backends/docs.py::docs_catalog
- tests/backend/tools/astloom-cli/test_docs_catalog.py::test_build_catalog_vocabularies_are_observed_not_hardcoded
- tests/backend/tools/astloom-cli/test_docs_link_sync.py::login
related_docs:
- as.doc.ckg.hybrid-documentation-coverage
- as.doc.ckg.ingestion-and-living-documentation-workflow
- as.doc.master.documentation-classification-lanes
- as.doc.agents.team-handout-astloom-documentation-complete
language: en
security_classification: internal
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Documentation Catalog and Lane Cache

## Purpose

Give coding agents a **small, cacheable index** of product Markdown (tags, closed-set lanes,
title, path) so they can decide which documents to Read before writing code—without dumping
full doc bodies into context and without inventing graph edges.

## Goals and Non-Goals

### Goals

- Expose **observed** vocabularies (tags/lanes/doc_type/…) from each software’s scanned Markdown.
- Index frontmatter across configurable roots (env/CLI/MCP; defaults for this checkout).
- Persist a rebuildable cache under `.astloom/cache/docs-catalog.json`.
- Filter by tag, concern, lifecycle, audience, phase, doc_type, query, linked_symbols presence.
- Wire CLI + MCP for the same payload shape.

### Non-Goals

- Auto-writing `DOCUMENTED_BY` from **tags or catalog metadata** alone (no tag→symbol edges).
- Replacing Full-tier authoring law or `docs-standards` gates.
- Full-text embedding search over Markdown bodies (optional future).

**Allowed (Phase 2):** catalog may **order** the docs queue; evidence path citations may
merge into `linked_symbols` and create edges **only after resolve** (same rules as
`docs-suggest-links`).

## Data Model

| Field | Source |
| --- | --- |
| `vocabularies` | **Observed** values from scanned frontmatter (tags, lanes, doc_type, phase, status, …) |
| `lane_enums` | Alias of observed lane-like keys only (same software — **not** a global hardcoded enum) |
| `tags` | Aggregated unique tags with counts from this scan |
| `documents[]` | One row per Markdown file that has YAML frontmatter |
| `vocabulary_source` | Always `observed_frontmatter` |
| `stats` | Counts for documents, tags, linked_symbols presence |
| `invents_edges` | Always `false` |

**Important:** each product/software tree may use its own tags and lane strings. The catalog
never injects Astloom procedure-09 closed sets into the vocabulary. Those closed sets remain
an authoring gate for Astloom product docs (`docs-standards`), separate from retrieval indexing.

Document row (compact): `path`, `doc_id`, `title`, `summary` (truncated), `tags`, `doc_type`,
`phase`, `status`, lanes, `linked_symbols_count`, `has_linked_symbols`.

## Scan roots (per software)

| Priority | Source |
| --- | --- |
| 1 | MCP/CLI `roots` argument |
| 2 | Env `ASTLOOM_DOCS_CATALOG_ROOTS` (comma-separated) |
| 3 | Built-in defaults for this Astloom checkout (`docs`, `backend/docs`, …) |

Other products should set `ASTLOOM_DOCS_CATALOG_ROOTS` (or pass `roots`) to their handbook trees.

## Cache

| Item | Default |
| --- | --- |
| Path | `.astloom/cache/docs-catalog.json` (gitignored via `.astloom/`) |
| Override | `ASTLOOM_DOCS_CATALOG_CACHE` absolute path |
| Roots override | `ASTLOOM_DOCS_CATALOG_ROOTS` or CLI/MCP `roots` |
| Rebuild | At the **start** of `astloom sync` (automatic), or `astloom docs-catalog --refresh` / MCP `refresh: true` |
| Schema | `schema_version: "1.1"` — mismatch forces rebuild |

```mermaid
flowchart TD
  disk[Markdown trees on disk] --> build[build_docs_catalog]
  build --> cache[.astloom/cache/docs-catalog.json]
  cache --> filter[filter_docs_catalog]
  mcp[astloom_docs_catalog] --> filter
  cli[astloom docs-catalog] --> filter
  filter --> agent[Agent picks paths to Read]
  build --> syncStart[astloom sync start]
  syncStart --> phase1[Phase 1 code ingest]
  phase1 --> phase2[Phase 2 sync_human_docs]
  cache --> phase2
  phase2 --> evidence[Evidence extract + optional FM apply]
  evidence --> resolve{Token resolves?}
  resolve -->|yes| edges[DOCUMENTED_BY]
  resolve -->|no| report[Unresolved report only]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Operator / agent | Start `astloom sync` (catalog builds first) | Catalog + observed vocabularies ready |
| 2 | Sync Phase 2 | Order discovered docs using catalog + evidence signals | Evidence / `lifecycle_lane: current` first |
| 3 | Sync Phase 2 | Extract evidence tokens; merge into `linked_symbols` (default apply to FM) | Tokens durable; still no edge without resolve |
| 4 | Sync Phase 2 | Resolve tokens against Phase 1 graph | `DOCUMENTED_BY` only when resolved |
| 5 | Agent | Optional `docs-catalog` filter → Read Markdown | Short list of paths outside sync |

## Operator / Agent Surfaces

### CLI

```text
astloom docs-catalog
astloom docs-catalog --refresh
astloom docs-catalog --roots handbook,docs --refresh
astloom docs-catalog --tag ckg --concern standard --limit 20
astloom docs-catalog --query hybrid --json
astloom docs-catalog --linked-only
```

### MCP

Tool: `astloom_docs_catalog` (`maps_to: docs_sync.catalog`).

Arguments: `refresh`, `roots`, `tag`, `concern_lane`, `lifecycle_lane`, `audience_lane`, `phase`,
`doc_type`, `query`, `has_linked_symbols`, `limit`.

## Relationship to Hybrid Coverage

| Mechanism | Role |
| --- | --- |
| Docs catalog | **Find** Markdown by metadata; **order** Phase 2 queue when cache is present |
| `docs-suggest-links` | Dry-run / review evidence `linked_symbols` (optional before sync) |
| `astloom sync` Phase 2 | Merge evidence (default), project human docs, write `DOCUMENTED_BY` for resolved tokens |
| `generation_context.hybrid_documentation` | Prefer human docs when edges exist |

### Sync env toggles (Phase 2 evidence)

| Env | Default | Effect |
| --- | --- | --- |
| `ASTLOOM_SYNC_DOCS_EVIDENCE` | on | Extract evidence tokens during Phase 2 and merge into link tokens |
| `ASTLOOM_SYNC_DOCS_EVIDENCE_APPLY` | on | Persist new evidence tokens into YAML `linked_symbols` (same as `docs-suggest-links --apply`) |

Unset or `0` / `false` / `no` / `off` disables. Tags and catalog lanes never create edges by themselves.

## Verification

| Check | How |
| --- | --- |
| Build + filter | `tests/backend/tools/astloom-cli/test_docs_catalog.py` |
| Phase 2 evidence + order | `tests/backend/tools/astloom-cli/test_docs_link_sync.py` |
| MCP profile | `astloom_docs_catalog` present in `programming-cursor-mcp` |
| Manual | `astloom docs-catalog --refresh --json \| head` |

## Related Documents

- [`41-hybrid-documentation-coverage.md`](./41-hybrid-documentation-coverage.md)
- [`../00-master-plan/09-documentation-classification-and-lanes.md`](../00-master-plan/09-documentation-classification-and-lanes.md)
- [`../agents/TEAM-HANDOUT-astloom-documentation-complete.md`](../agents/TEAM-HANDOUT-astloom-documentation-complete.md)
