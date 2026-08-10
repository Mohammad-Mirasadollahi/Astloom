---
doc_id: as.doc.ckg.code-metadata-schema-and-lifecycle
title: 08 - Code Metadata Schema And Lifecycle
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the low-level metadata model and lifecycle for metadata-first
  code understanding.
tags:
- standard
- ckg
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/08-code-metadata-schema-and-lifecycle.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 08 - Code Metadata Schema And Lifecycle

## Purpose

This document defines the low-level metadata model and lifecycle for metadata-first code understanding.

## Metadata Records

### FileMetadata

Represents a source file without requiring the full file body.

Required fields:

- file_id
- project_id
- repository_id
- path
- language
- module_name
- content_hash
- ast_hash
- line_count
- symbol_count
- primary_responsibility
- exported_symbols
- imported_modules
- framework_markers
- risk_tags
- owner
- last_indexed_at
- freshness_status
- confidence_score

### SymbolMetadata

Represents a function, method, class, type, module, component, route, command, handler, job, migration, or test.

Required fields:

- symbol_id
- file_id
- qualified_name
- symbol_type
- visibility
- signature
- parameters
- return_type
- responsibility_summary
- behavior_summary
- side_effects
- dependencies
- callers
- callees
- related_tests
- related_docs
- related_decisions
- related_rules
- complexity_score
- risk_tags
- source_span
- symbol_hash
- metadata_version
- confidence_score

### DependencyMetadata

Represents imports, package dependencies, service calls, database access, message topics, HTTP clients, SDK usage, and external provider usage.

Required fields:

- dependency_id
- source_symbol_id
- target_ref
- dependency_type
- resolution_status
- confidence_score
- risk_tags
- evidence

### TestMetadata

Represents tests linked to files and symbols.

Required fields:

- test_id
- test_type
- path
- covered_symbols
- fixture_refs
- last_result
- last_run_at
- confidence_score

### MetadataEvidence

Every metadata record must preserve evidence:

- extractor_name
- extractor_version
- source_hash
- parser_version
- generated_at
- source_span
- confidence_reason
- known_unknowns

## Lifecycle

1. File discovered or changed.
2. Hash service computes content and AST hashes.
3. Extractors produce normalized metadata records.
4. Metadata validator checks required fields, confidence, source spans, and schema compatibility.
5. Metadata store upserts records by stable ids.
6. Code graph relationships are updated.
7. Embeddings and text indexes are refreshed where needed.
8. Drift detector compares metadata freshness against source hashes.
9. Retrieval service uses metadata for context packs.
10. Source escalation events update effectiveness metrics.

## Freshness States

- `CURRENT`: metadata hash matches source hash.
- `STALE`: source changed after metadata extraction.
- `PARTIAL`: metadata exists but some extractors failed.
- `FAILED`: metadata generation failed.
- `UNKNOWN`: freshness cannot be verified.

## Confidence Rules

Confidence should be calculated from parser quality, language support, extraction completeness, call resolution quality, source hash match, test linkage, and previous successful usage.

Confidence must be data-driven. Thresholds belong in `backend/configs/code-metadata-profiles`.

## Source Escalation Policy

The resolver must recommend source reads when:

- freshness is not CURRENT.
- confidence is below threshold.
- risk tags include security, authz, authn, persistence, migration, billing, deployment, secrets, concurrency, or destructive operations.
- the task requires exact behavior.
- a generated patch would modify the symbol.
- metadata has unresolved dependencies.
- tests failed near the symbol.

## Anti-Patterns

- Do not use metadata as an excuse to avoid reading code for high-risk changes.
- Do not inject large metadata blobs that are as expensive as source code.
- Do not hard-code ranking weights.
- Do not share metadata across isolated projects unless project-group policy allows it.
- Do not trust AI-generated summaries without hashes, source spans, and confidence metadata.
