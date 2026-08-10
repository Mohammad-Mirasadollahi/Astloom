# Code Metadata Package

Path: `backend/packages/code-metadata`

## Purpose

Provides shared contracts and reusable primitives for metadata-first code understanding. The package defines how Astloom represents compact code metadata so agents can inspect a lightweight, indexed view before reading full source files.

The goal is to reduce token usage, improve code navigation, increase retrieval precision, and make agent decisions more explainable.

## Contents

- `contracts/` versioned metadata schemas for files, symbols, dependencies, behavior summaries, freshness, risk, and evidence.
- `extractors/` future interfaces for AST, static analysis, documentation, test, ownership, and dependency metadata extraction.
- `ranking/` future reusable scoring interfaces for metadata relevance and source-read escalation.
- `context-packs/` future structures for compact bundles passed to agents.
- `examples/` sample metadata records and retrieval scenarios.

## Dependency Rules

This package may depend on stable contracts and shared-kernel primitives. It must not depend on deployable services, database clients, Neo4j drivers, parser implementations, or UI code.

## Status

Active. Profile loader and `should_escalate_to_source` are used by `code-graph-service`
generation-context packs. File/symbol contract validators run during ingest and attach
validated `code_metadata` records onto graph symbol metadata (`code_metadata_bridge`).

Normative wiring + unused-candidate classification:
`docs/07-code-knowledge-graph/79-shared-package-wiring-and-unwired-findings.md`.
