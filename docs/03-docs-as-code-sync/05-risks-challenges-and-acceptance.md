---
doc_id: as.doc.docs-sync.risks-challenges-and-acceptance
title: Docs-as-Code and Synchronization - Risks, Challenges, and Acceptance
doc_type: gap
status: draft
schema_version: '1.0'
owner: platform-docs
summary: '- AST hashes must ignore formatting noise but catch behavior-changing edits. - Bloom
  filters can have false positives; positive hits need graph verification. - Inline doc flags
  are cheap but can become stale unless CI reconciles them. - Docs should remain readable
  by humans while.'
tags:
- gap
- docs-sync
phase: 03-docs-as-code-sync
canonical_path: docs/03-docs-as-code-sync/05-risks-challenges-and-acceptance.md
lifecycle_lane: future
concern_lane: gap
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Docs-as-Code and Synchronization - Risks, Challenges, and Acceptance


## Purpose

- AST hashes must ignore formatting noise but catch behavior-changing edits. - Bloom filters can have false positives; positive hits need graph verification. - Inline doc flags are cheap but can become stale unless CI reconciles them. - Docs should remain readable by humans while.

## Challenges

- AST hashes must ignore formatting noise but catch behavior-changing edits.
- Bloom filters can have false positives; positive hits need graph verification.
- Inline doc flags are cheap but can become stale unless CI reconciles them.
- Docs should remain readable by humans while carrying enough metadata for agents.
- A merge gate must distinguish critical missing docs from low-value helper functions.

## Mitigation Strategy

- Normalize AST input before hashing.
- Keep Bloom filter versions tied to graph snapshots.
- Validate frontmatter and doc flags in CI.
- Use severity rules for public APIs, security-sensitive modules, data contracts, and domain logic.
- Convert drift findings into Issues and Docs Agent Tasks with clear acceptance criteria.

## Acceptance Criteria

- A changed documented function produces a drift finding before merge.
- Markdown frontmatter is validated automatically and remains human-readable.
- Agents can quickly determine whether a symbol has required documentation without scanning the whole repository.
- Every drift finding creates or links to an Issue and, when actionable, a Docs Agent Task.
