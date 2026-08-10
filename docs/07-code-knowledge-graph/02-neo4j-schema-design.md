---
doc_id: as.doc.ckg.neo4j-schema-design
title: Code-Knowledge Graph - Neo4j Schema Design
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: The **canonical Neo4j runtime model** for `code-graph-service` is:.
tags:
- standard
- ckg
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/02-neo4j-schema-design.md
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

# Code-Knowledge Graph - Neo4j Schema Design


## Purpose

The **canonical Neo4j runtime model** for `code-graph-service` is:.

## Runtime projection (normative for Phase 7)

The **canonical Neo4j runtime model** for `code-graph-service` is:

- Label `CodeSymbol` with a `kind` property (`file`, `class`, `function`, `method`, `import`, `module`, `documentation`, …)
- Relationship type `CODE_REL` with a `rel_type` property (`CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS_FROM`, `DOCUMENTED_BY`, `ROUTES_TO`, `TESTED_BY`, `HTTP_CALLS`, `ASYNC_CALLS`)

See ADR: `13-codesymbol-projection-adr.md`. The typed catalog below is the **logical product vocabulary** and a future optional enrichment path — not what `Neo4jStore` writes today.

## Database Choice

Neo4j is the primary graph database for the Code-Knowledge Graph. It is responsible for storing structural code relationships and supporting graph traversal. Semantic embeddings are stored in PostgreSQL with pgvector; Neo4j stores graph structure and traversal state only.

## Core Node Types (logical catalog)

### Project

Represents a repository or workspace.

Properties:

- `project_id`
- `name`
- `root_path`
- `default_branch`
- `language_set`
- `last_indexed_commit`

### File

Represents a source or documentation file.

Properties:

- `file_id`
- `path`
- `language`
- `content_hash`
- `last_indexed_at`
- `doc_required`
- `status`

### Class

Represents a class or equivalent type declaration.

Properties:

- `class_id`
- `name`
- `qualified_name`
- `signature`
- `code_snippet`
- `hash_value`
- `ai_documentation`
- `embedding_ref`
- `visibility`

### Function

Represents a function or module-level callable.

Properties:

- `function_id`
- `name`
- `qualified_name`
- `signature`
- `parameters`
- `return_type`
- `code_snippet`
- `hash_value`
- `ai_documentation`
- `embedding_ref`
- `visibility`
- `doc_status`

### Method

Represents a class method.

Properties are similar to Function, with additional class ownership fields.

### Import

Represents an imported package, module, symbol, or file dependency.

Properties:

- `import_id`
- `source_text`
- `resolved_target`
- `is_external`
- `package_name`

## Core Relationships

### CONTAINS

Connects Project to File, File to Class, File to Function, and Class to Method.

Examples:

```text
(Project)-[:CONTAINS]->(File)
(File)-[:CONTAINS]->(Class)
(File)-[:CONTAINS]->(Function)
(Class)-[:CONTAINS]->(Method)
```

### CALLS

Connects one Function or Method to another callable.

Properties:

- `call_site`
- `line_range`
- `confidence`
- `resolution_status`

### INHERITS_FROM

Connects a Class to its parent Class.

Properties:

- `confidence`
- `resolved_by`

### IMPORTS

Connects File to Import or File to File when import resolution is possible.

Properties:

- `import_text`
- `is_external`
- `confidence`

### DOCUMENTED_BY

Connects code nodes to generated or human-authored docs.

### HAS_EMBEDDING

Optional relationship to an embedding reference record. The embedding vector itself is stored in PostgreSQL pgvector.

### GENERATED_FROM

Connects AI-generated documentation or generated code to the source graph context used to create it.

## Required Indexes

Neo4j indexes should exist for:

- `Project.project_id`
- `File.path`
- `File.content_hash`
- `Function.qualified_name`
- `Function.hash_value`
- `Class.qualified_name`
- `Method.qualified_name`
- graph indexes for traversal entry points; embedding indexes live in PostgreSQL pgvector

## Constraints

- A File path must be unique within a Project.
- A qualified symbol name must be unique within a File revision.
- A code node hash must be tied to parser version and normalization version.
- A generated documentation entry must reference the code hash it describes.
- A CALLS relationship with low confidence must not be used for high-risk impact automation without verification.

## Hash Strategy

The `hash_value` should not be a naive raw string hash when semantic precision matters. The recommended approach is a normalized AST hash.

Hash input should include:

- normalized symbol body,
- normalized signature,
- parser version,
- language version when available.

Hash input should exclude:

- formatting-only changes,
- comments unless they affect doc flags,
- unstable line numbers.

## Embedding Strategy

Embeddings should be generated from compact semantic text, not necessarily full raw code.

Recommended embedding text:

```text
symbol qualified name
signature
AI documentation summary
important call targets
domain tags
```

This keeps embeddings cheaper, smaller, and more semantically useful for retrieval.

## Retrieval Profile Contract

Graph retrieval behavior should be configurable through `GraphRetrievalProfile` records or equivalent external configuration.

Recommended contract:

- `GraphRetrievalProfile(id, tenant_id, repository_id, task_type, risk_level, version, feature_weights, expansion_limits, confidence_thresholds, status)`

Contract rules:

- Final graph ranking weights must not be hard-coded.
- Default profiles are allowed, but they must be versioned and adjustable without code deployment.
- Security-sensitive repositories may prioritize active Decisions and owner verification.
- Documentation tasks may prioritize documentation freshness and parser confidence.
- Code generation tasks may prioritize graph proximity, symbol authority, and successful prior usage.
