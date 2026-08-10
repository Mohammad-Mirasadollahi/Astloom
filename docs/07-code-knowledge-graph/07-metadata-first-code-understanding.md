---
doc_id: as.doc.ckg.metadata-first-code-understanding
title: 07 - Metadata-First Code Understanding
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom should use a metadata-first code understanding strategy.
tags:
- standard
- ckg
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/07-metadata-first-code-understanding.md
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

# 07 - Metadata-First Code Understanding


## Purpose

Astloom should use a metadata-first code understanding strategy. The system should not read the full source code as the default first step. It should first inspect compact, structured, indexed metadata and then read source code only when the metadata is insufficient, stale, low.

## Position

Astloom should use a metadata-first code understanding strategy. The system should not read the full source code as the default first step. It should first inspect compact, structured, indexed metadata and then read source code only when the metadata is insufficient, stale, low-confidence, ambiguous, or when the requested action is high-risk.

This design gives Astloom a practical advantage: faster retrieval, lower token usage, better explainability, and stronger code navigation across large repositories.

## Core Idea

Every relevant code artifact should have a metadata record. Metadata describes the code enough for initial reasoning:

- what the file or symbol is responsible for.
- public API and signature.
- dependencies and call relationships.
- important side effects.
- data access and external integrations.
- related tests and docs.
- ownership and change history.
- freshness and confidence.
- whether source code must be read before modifying it.

Agents receive a metadata context pack first. If the context pack is enough, the agent can plan, search, classify, document, review, or propose changes without loading entire files. If not enough, the agent escalates to targeted source reads.

## High-Level Architecture

Metadata-first understanding is implemented through these components:

- Repository Scanner discovers files and change sets.
- Parser Extractors generate AST-based symbols, signatures, imports, calls, and inheritance metadata.
- Static Analysis Extractors generate complexity, side effects, security markers, data access, and framework-specific metadata.
- Documentation Extractors link existing docs, comments, generated summaries, and drift status.
- Test Extractors link symbols to unit, integration, live, and contract tests.
- Metadata Store stores current metadata, versions, freshness, confidence, and evidence.
- Code Graph Store links metadata to File, Symbol, Call, Import, Test, Doc, Decision, Rule, and Task nodes.
- Retrieval Service builds compact metadata context packs.
- Source Escalation Policy decides when full source code must be read.

## Metadata-First Flow

1. A task arrives with project, repository, workflow type, risk level, and user intent.
2. The retrieval service searches metadata using text, vector, graph, tags, ownership, and dependency signals.
3. Candidate metadata records are ranked by relevance, freshness, confidence, authority, risk, and token efficiency.
4. A compact context pack is returned to the agent.
5. The agent performs initial reasoning from metadata.
6. If escalation rules are triggered, the agent reads only the required source slices.
7. The final answer or patch records which metadata and source slices were used.

## When Metadata Is Enough

Metadata may be enough for:

- locating the right module or function.
- understanding ownership and dependency direction.
- generating documentation outlines.
- estimating impact areas.
- identifying related tests.
- detecting likely duplicate code.
- deciding whether a task needs backend, frontend, database, or integration work.
- preparing a code review checklist.

## When Source Code Must Be Read

Full or partial source must be read when:

- metadata is stale or missing.
- confidence is below the configured threshold.
- a change modifies logic, security, permissions, persistence, money, identity, deployment, or migrations.
- the task asks for exact implementation behavior.
- call resolution is ambiguous.
- generated code would modify a symbol.
- tests fail and metadata does not explain the failure.
- metadata and source hashes disagree.

## Expected Benefits

- lower token consumption.
- faster first response and planning.
- less unnecessary code scanning.
- better retrieval precision.
- safer source-read decisions.
- better auditability because the agent can cite metadata records and source escalation reasons.
- stronger multi-agent coordination because agents can share structured context packs instead of large source dumps.
