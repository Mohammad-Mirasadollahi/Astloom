---
doc_id: as.doc.tech.docs-sync-technical-logic
title: Docs-as-Code Synchronization Technical Logic
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: The Docs-as-Code layer must detect when documentation is missing, stale, or incorrectly
  linked to code. It does this through code indexing, documentation indexing, graph linking,
  AST anchors, Bloom filter lookup, and CI enforcement.
tags:
- standard
- tech
phase: 06-technical-logic
canonical_path: docs/06-technical-logic/03-docs-sync-technical-logic.md
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

# Docs-as-Code Synchronization Technical Logic


## Purpose

The Docs-as-Code layer must detect when documentation is missing, stale, or incorrectly linked to code. It does this through code indexing, documentation indexing, graph linking, AST anchors, Bloom filter lookup, and CI enforcement.

## Technical Goal

The Docs-as-Code layer must detect when documentation is missing, stale, or incorrectly linked to code. It does this through code indexing, documentation indexing, graph linking, AST anchors, Bloom filter lookup, and CI enforcement.

## Code Indexing Pipeline

```text
for each repository_revision:
    discover files by language and ownership rules
    parse files with language-specific parser
    extract symbols and public interfaces
    normalize signatures
    compute symbol hashes
    compute dependency edges
    persist CodeSymbol records
    emit code.symbol_indexed events
```

Symbol extraction should include:

- functions,
- classes,
- methods,
- API routes,
- database schemas,
- event contracts,
- configuration keys,
- security-sensitive logic,
- public interfaces.

## AST Anchor Logic

A stable AST anchor should identify semantic code rather than physical lines.

Anchor components:

```text
anchor_id = hash(
    repo_id,
    file_path,
    language,
    symbol_path,
    symbol_kind,
    normalized_signature
)
```

Body hash components:

```text
body_hash = hash(normalized_ast_body_without_formatting_noise)
```

The anchor identifies the symbol. The body hash detects behavior change.

## Normalization Rules

The normalizer should ignore:

- whitespace,
- comments that are not doc flags,
- formatting-only changes,
- import ordering when behavior does not change,
- generated line numbers.

The normalizer should detect:

- changed control flow,
- changed conditionals,
- changed constants,
- changed API parameters,
- changed data schema fields,
- changed security behavior,
- changed side effects.

## Documentation Indexing Pipeline

```text
for each markdown_doc:
    parse frontmatter
    validate required metadata
    parse headings and anchors
    extract linked_symbols
    extract decision_refs and issue_refs
    persist Doc records
    persist DocAnchor records
    emit doc.indexed events
```

A document without valid frontmatter can still be readable by humans, but it should not be treated as synchronized technical documentation.

## Graph Linking Logic

The graph linker creates edges between Docs, CodeSymbols, Decisions, Issues, Tasks, Rules, and Owners.

Important link rules:

- A DocAnchor links one Doc to one CodeSymbol and recorded hash.
- A Decision can link to many CodeSymbols and Docs.
- A DriftFinding links current CodeSymbol hash to stale DocAnchor hash.
- Ownership edges determine reviewers and escalation paths.

## Drift Detection Algorithm

```text
for each CodeSymbol changed in revision:
    anchors = graph.find_doc_anchors(CodeSymbol.id)

    if symbol.doc_required and anchors.empty:
        create DriftFinding(type=MISSING_DOC)
        continue

    for anchor in anchors:
        if anchor.recorded_hash != CodeSymbol.body_hash:
            create DriftFinding(type=STALE_DOC)
        else:
            mark anchor as SYNCED
```

Drift severity should depend on symbol type and domain.

Severity rules:

- Public API route changed: high.
- Authentication or authorization logic changed: critical.
- Billing or pricing logic changed: critical.
- Internal helper changed with `doc: n`: low or none.
- Data contract changed: high.
- Migration script changed: high.

## Bloom Filter Logic

The Bloom filter stores documented symbol IDs for fast negative lookup.

Build process:

```text
symbols = graph.query_symbols_with_docs(index_version)
filter = BloomFilter(expected_count=len(symbols), false_positive_rate=target_rate)
for symbol_id in symbols:
    filter.add(symbol_id)
publish filter with version
```

Lookup behavior:

- Negative result: symbol definitely has no doc in this version.
- Positive result: symbol may have docs, verify through graph.

This reduces expensive graph queries when scanning large codebases.

## Doc Flag Reconciliation

Doc flags can be inline or manifest-based.

Reconciliation logic:

```text
for each CodeSymbol:
    expected = resolve_doc_flag(symbol)
    graph_has_doc = graph.exists_doc_anchor(symbol)

    if expected == true and not graph_has_doc:
        create MISSING_DOC finding
    if expected == false and graph_has_doc:
        create OPTIONAL_DOC_LINK finding or update manifest
    if expected is unknown:
        classify using public_api, security, billing, schema, ownership rules
```

## CI Gate Logic

CI should fail only for actionable documentation risks.

Gate decision:

```text
if any critical drift finding:
    fail merge
elif high drift finding and no approved waiver:
    fail merge
elif medium drift finding:
    warn and create task
else:
    pass
```

A waiver must include owner, reason, expiration, and linked Issue.

## Frontmatter Validation Logic

Required fields:

- `doc_id`,
- `title`,
- `owner`,
- `status`,
- `schema_version`,
- `linked_symbols`.

Validation failures:

- missing required field,
- invalid owner,
- linked symbol not found,
- recorded hash mismatch,
- stale schema version,
- invalid status transition.

## Failure Handling

- If parser fails, create `code.index_failed` and do not assume docs are synced.
- If doc frontmatter is invalid, create validation Issue and exclude doc from sync status.
- If Bloom filter is stale, fall back to graph lookup.
- If symbol rename confidence is low, create review Task instead of auto-relinking.
