---
doc_id: as.doc.docs-sync.index
title: 03 - Docs-as-Code and Synchronization Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: Make documentation, code, decisions, and ownership part of one synchronized knowledge
  graph so documentation drift is detected before merge.
tags:
- index
- docs-sync
phase: 03-docs-as-code-sync
canonical_path: docs/03-docs-as-code-sync/00-index.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols:
- backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs
- backend/services/code-graph-service/src/code_graph_service/application/ingest/human_docs.py::HumanDocIngestMixin
- backend/packages/astloom_cli/docs_registry_hygiene.py::purge_docs_registry_fixture_noise
doc_version: 1.0.3
updated_at: 2026-08-10
---

# 03 - Docs-as-Code and Synchronization Index


## Purpose

Make documentation, code, decisions, and ownership part of one synchronized knowledge graph so documentation drift is detected before merge.

## Mission

Make documentation, code, decisions, and ownership part of one synchronized knowledge graph so documentation drift is detected before merge.

## Files

- `01-feature-specification.md` defines documentation synchronization features and requirements.
- `02-high-level-design.md` defines actors, components, sync flow, integrations, and reliability requirements.
- `03-low-level-design.md` defines AST anchors, hash generation, frontmatter validation, drift detection, Bloom filter lookup, and CI gate rules.
- `04-data-contracts-and-events.md` defines docs, code symbol, graph, and drift contracts.
- `05-risks-challenges-and-acceptance.md` defines risks and acceptance criteria.
- `06-detailed-section-design.md` provides deep rationale, graph design, AST anchor details, drift behavior, edge cases, and phase output.
- Sister cleanup loop (scored stale-doc candidates): `../07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md` (`astloom_docs_stale_candidates`; finding kinds include `wiki_orphan` / `duplicate_authority`).

## Features Covered

- Documentation Knowledge Graph
- AST Anchoring
- YAML Frontmatter
- Bloom Filter Lookup
- Drift Detection / CI Gate
- Scored stale-documentation candidates (MCP; Astloom never deletes Markdown)
- Lightweight y/n Doc Flags

## Related Technical Logic

- `../06-technical-logic/03-docs-sync-technical-logic.md` explains code indexing, AST anchors, documentation graph linking, drift detection, Bloom filters, and CI merge gates.

## Related Authoring Standard

- `../00-master-plan/08-documentation-structure-and-machine-ingest-standard.md` defines how authors must structure files, headings, frontmatter, RAG chunks, GraphRAG relations, and fallback-readable bodies so docs-sync and retrieval stacks can ingest them optimally.

## Operator sync bridge

`astloom sync` Phase 2 walks `doc_paths`, indexes Markdown into this service (Document + DocAnchor), and projects `DOCUMENTED_BY` edges into the Code-Knowledge Graph for resolved `linked_symbols`. See [03 - Ingestion and Living Documentation Workflow §10](../07-code-knowledge-graph/03-ingestion-and-living-documentation-workflow.md) and [42 - Astloom CLI Command Reference § Sync filters](../08-software-engineering-architecture/42-astloom-cli-command-reference.md#sync-filters).

### Docs registry fixture hygiene

Live QA can leave intentional docs-sync symbol rows whose paths contain `never_linked`, `ghost_`, or `never_should_exist`. Those rows pollute `docs_status` coverage. Best-effort purge runs from `astloom quality-audit`, MCP `astloom_quality_audit`, and sync follow-up (`purge_docs_registry_fixture_noise` in `astloom_cli.docs_registry_hygiene`) — unregister only matching fixture noise; never fails the caller.
