---
doc_id: as.doc.docs-sync.feature-specification
title: Docs-as-Code and Synchronization - Feature Specification
doc_type: feature_spec
status: draft
schema_version: '1.0'
owner: platform-docs
summary: This phase makes documentation, code, decisions, and ownership part of one synchronized
  knowledge graph so documentation drift is detected before merge.
tags:
- feature-spec
- docs-sync
phase: 03-docs-as-code-sync
canonical_path: docs/03-docs-as-code-sync/01-feature-specification.md
lifecycle_lane: future
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols:
- backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs
- backend/services/code-graph-service/src/code_graph_service/domain/doc_discovery.py::discover_documentation_files
doc_version: 1.0.2
updated_at: 2026-08-10
---

# Docs-as-Code and Synchronization - Feature Specification


## Purpose

This phase makes documentation, code, decisions, and ownership part of one synchronized knowledge graph so documentation drift is detected before merge.

## Document flow

```mermaid
flowchart TD
  reader[Reader] --> doc[This document]
  doc --> next[Related docs or implementation]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Reader | Opens this design document | Understands scope and constraints |
| 2 | Reader | Follows the Mermaid flow | Sees primary component interactions |
| 3 | Reader | Uses Related Documents / linked symbols | Reaches deeper design or implementation |


## Mission

This phase makes documentation, code, decisions, and ownership part of one synchronized knowledge graph so documentation drift is detected before merge.

## Feature 1 - Documentation Knowledge Graph

Documents, code symbols, APIs, decisions, tasks, rules, and owners are modeled as linked graph entities. Documentation is not isolated text; it is part of the active system model.

## Feature 2 - AST Anchoring

Code symbols are anchored using parser-derived semantic identifiers and normalized hashes. This allows the system to detect meaningful code changes without relying on fragile line numbers.

## Feature 3 - YAML Frontmatter

Markdown documentation includes structured metadata such as doc ID, owner, status, linked symbols, schema version, current hash, and decision references.

## Feature 4 - Bloom Filter Lookup

An in-memory Bloom filter allows agents to quickly skip code symbols that definitely have no documentation in the current index version.

## Feature 5 - Lightweight y/n Doc Flags

Code comments or manifests can mark whether a symbol is expected to have documentation. CI reconciles these flags with the graph.

## Functional Requirements

- Index source symbols and documentation metadata.
- Link documents to code symbols and decisions.
- Detect stale or missing documentation.
- Create DriftFindings and Docs Agent Tasks.
- Block merges for critical documentation drift.
- Keep documents readable by humans and routable by machines.
- Surface scored stale-documentation candidates for agent cleanup (`astloom_docs_stale_candidates`; normative detail in `../07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md`). Astloom never deletes Markdown.

## Related Documents

- [`../07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md`](../07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md) — scored stale-doc cleanup loop (sister to dead-code).
- [`00-index.md`](00-index.md) — docs-as-code phase index.
