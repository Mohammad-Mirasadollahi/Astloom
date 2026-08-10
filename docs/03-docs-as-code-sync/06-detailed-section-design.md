---
doc_id: as.doc.docs-sync.detailed-section-design
title: Docs-as-Code and Synchronization - Detailed Section Design
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Documentation drift is one of the oldest problems in software engineering. Code changes
  quickly, but documents are often updated late or not updated at all. In an AI-agent environment,
  the problem becomes more dangerous because future agents may trust stale docs and make incorrec.
tags:
- standard
- docs-sync
phase: 03-docs-as-code-sync
canonical_path: docs/03-docs-as-code-sync/06-detailed-section-design.md
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

# Docs-as-Code and Synchronization - Detailed Section Design


## Purpose

Documentation drift is one of the oldest problems in software engineering. Code changes quickly, but documents are often updated late or not updated at all. In an AI-agent environment, the problem becomes more dangerous because future agents may trust stale docs and make incorrec.

## Why This Phase Exists

Documentation drift is one of the oldest problems in software engineering. Code changes quickly, but documents are often updated late or not updated at all. In an AI-agent environment, the problem becomes more dangerous because future agents may trust stale docs and make incorrect changes at high speed.

This phase makes documentation part of the living system state.

## Documentation Knowledge Graph in Detail

The documentation graph represents relationships between documents, code symbols, files, APIs, data schemas, Decisions, Issues, Tasks, Rules, owners, and teams.

A document should not only say what a function does. It should also know which function it explains, which Decision justified the design, which API consumers depend on it, which owner reviews it, and whether it is synchronized with current code.

### Important Edge Types

- `explains`: a document explains a code symbol or API.
- `implements`: a code symbol implements a requirement or Decision.
- `depends_on`: one entity relies on another.
- `supersedes`: a newer doc or Decision replaces an older one.
- `owned_by`: an entity is owned by a team or person.
- `blocks_merge`: a drift finding prevents merge.
- `requires_review`: a change needs a human reviewer.

## AST Anchoring in Detail

Line numbers are fragile because formatting changes can move code. AST anchors are more stable because they are based on semantic structure.

A good anchor should include:

- Repository identity.
- File path.
- Symbol path.
- Symbol kind.
- Normalized signature.
- Body hash that ignores formatting noise.
- Language and parser version.

When a documented symbol changes, the new hash is compared with the hash recorded in the linked document. If the hash changed, the system creates a drift finding.

## YAML Frontmatter in Detail

Frontmatter makes Markdown machine-readable without making it unreadable for humans. It lets agents route documents before reading full content.

A complete document should include:

- `doc_id`
- `title`
- `owner`
- `status`
- `schema_version`
- `linked_symbols`
- `decision_refs`
- `reviewed_by`
- `reviewed_at`
- `current_hash`
- `related_issues`
- `supersedes`

The body of the document should explain behavior, constraints, examples, failure modes, and operational notes.

## Bloom Filter Lookup in Detail

The Bloom filter is a performance optimization. It is useful when agents scan many symbols and need to know whether documentation might exist.

A negative Bloom filter result means the symbol definitely is not documented in the current index version. A positive result means documentation may exist and must be verified through the graph.

This reduces database queries and prevents agents from wasting time on temporary helper functions.

## Lightweight y/n Doc Flags in Detail

Not every function deserves documentation. A tiny helper may not need a full page. A public API, billing rule, security function, migration script, or data contract probably does.

Doc flags make expectations explicit:

- `doc: y`: documentation is required.
- `doc: n`: documentation is not required.
- missing flag: CI or a docs agent should classify or add a default.

Flags can live inline, in a manifest, or in generated code index metadata.

## Architecture Flow Notes

The docs system should run in CI and during agent work. It should not wait until release day. The drift detector should create actionable Issues and Tasks, not vague warnings.

A good drift finding says:

- Which symbol changed.
- Which doc is linked.
- Which hash changed.
- Why the doc may be stale.
- Which owner or Docs Agent should update it.
- Whether merge is blocked.

## Module Responsibility Notes

### Code Indexer

Parses repositories and extracts symbols, signatures, imports, API routes, schemas, and AST hashes.

### Documentation Indexer

Reads Markdown, validates frontmatter, extracts headings, links, anchors, and referenced Decisions.

### Graph Linker

Creates edges between docs, code, decisions, tasks, owners, and rules.

### Drift Detector

Compares current code hashes with documented hashes and produces DriftFindings.

### Coverage Index

Combines graph data, doc flags, manifest rules, and Bloom filter state to answer documentation coverage questions quickly.

## Edge Cases

- A function is renamed but behavior is unchanged: graph link should migrate if confidence is high or request review if not.
- Formatting changes alter line numbers: AST anchor should avoid false drift.
- A helper grows into business logic: doc flag should change from no to yes.
- A doc explains multiple symbols: each symbol needs independent anchor status.
- A symbol has docs but the doc is obsolete: coverage is not enough; sync status matters.

## Output of This Phase

At the end of this phase, documents are no longer passive files. They are indexed, linked, validated, and synchronized with the code and decisions they describe.
