---
doc_id: as.doc.docs-sync.data-contracts-and-events
title: Docs-as-Code and Synchronization - Data Contracts and Events
doc_type: contract
status: active
schema_version: '1.0'
owner: platform-docs
summary: '- `Doc(id, path, title, owner, status, version, linked_symbols, decision_refs)`
  - `CodeSymbol(id, repo, file_path, symbol_path, kind, signature_hash, body_hash, doc_required)`
  - `DocAnchor(id, doc_id, code_symbol_id, recorded_hash, status)` - `GraphEdge(id, source_id,
  target_id, .'
tags:
- contract
- docs-sync
phase: 03-docs-as-code-sync
canonical_path: docs/03-docs-as-code-sync/04-data-contracts-and-events.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Docs-as-Code and Synchronization - Data Contracts and Events


## Purpose

- `Doc(id, path, title, owner, status, version, linked_symbols, decision_refs)` - `CodeSymbol(id, repo, file_path, symbol_path, kind, signature_hash, body_hash, doc_required)` - `DocAnchor(id, doc_id, code_symbol_id, recorded_hash, status)` - `GraphEdge(id, source_id, target_id, .

## Core Entities

- `Doc(id, path, title, owner, status, version, linked_symbols, decision_refs)`
- `CodeSymbol(id, repo, file_path, symbol_path, kind, signature_hash, body_hash, doc_required)`
- `DocAnchor(id, doc_id, code_symbol_id, recorded_hash, status)`
- `GraphEdge(id, source_id, target_id, relation, confidence, created_by)`
- `DocCoverageEntry(symbol_id, doc_required, has_doc, lookup_source, last_checked_at)`
- `DriftFinding(id, symbol_id, doc_id, old_hash, new_hash, severity, status)`

## Events

- `code.symbol_indexed`
- `doc.indexed`
- `doc.frontmatter_invalid`
- `doc.anchor_changed`
- `drift.detected`
- `doc.coverage_updated`
- `ci.docs_gate_failed`

## Markdown Frontmatter Contract

Required fields:

- `doc_id`
- `title`
- `owner`
- `status`
- `linked_symbols`
- `decision_refs`
- `schema_version`

Optional fields:

- `current_hash`
- `reviewed_at`
- `reviewed_by`
- `supersedes`
- `related_issues`

## Contract Rules

- Bloom filter positive matches are hints and must be verified against the graph.
- Bloom filter negative matches can be treated as definite no-doc results within the filter generation version.
- AST hashes must ignore formatting-only changes but detect behavior-changing edits.
- CI must distinguish critical public APIs from low-value temporary helpers.
