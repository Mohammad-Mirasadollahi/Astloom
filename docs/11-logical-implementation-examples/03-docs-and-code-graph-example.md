---
doc_id: as.doc.examples.docs-and-code-graph-example
title: Logical Example - Docs and Code Graph
doc_type: example
status: draft
schema_version: '1.0'
owner: platform-docs
summary: A developer changes discount logic for VIP users. The Code-Knowledge Graph must detect
  the changed function, update graph relationships, detect stale documentation, and provide
  context for future code generation.
tags:
- example
- examples
phase: 11-logical-implementation-examples
canonical_path: docs/11-logical-implementation-examples/03-docs-and-code-graph-example.md
lifecycle_lane: current
concern_lane: example
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Logical Example - Docs and Code Graph


## Purpose

A developer changes discount logic for VIP users. The Code-Knowledge Graph must detect the changed function, update graph relationships, detect stale documentation, and provide context for future code generation.

## Scenario

A developer changes discount logic for VIP users. The Code-Knowledge Graph must detect the changed function, update graph relationships, detect stale documentation, and provide context for future code generation.

## Changed Code Symbol

```text
file: src/sales/discount.py
symbol: calculate_discount(amount, user_type, is_vip)
change: VIP users receive an additional discount rule.
```

## Ingestion Flow

```text
1. Git commit triggers indexing.
2. Tree-sitter parses src/sales/discount.py.
3. Symbol extractor finds calculate_discount.
4. Hash service computes normalized AST hash.
5. New hash differs from Neo4j stored hash.
6. AI documentation generation runs for changed symbol only.
7. Embedding is regenerated from signature and documentation summary.
8. Neo4j node is updated.
9. CALLS and IMPORTS relationships are refreshed.
10. Drift detector checks linked docs.
```

## Graph Upsert Result

```text
(File: src/sales/discount.py)-[:CONTAINS]->(Function: calculate_discount)
(Function: calculate_discount)-[:CALLS]->(Function: load_user_discount_policy)
(Function: calculate_discount)-[:DOCUMENTED_BY]->(Doc: discount-rules.md)
```

Function properties update:

```text
hash_value: new normalized hash
ai_documentation: updated VIP discount explanation
embedding: regenerated semantic vector
doc_status: STALE until linked doc is updated
```

## Drift Finding

The linked document still says discounts depend only on user type and amount.

Created record:

```text
DriftFinding:
    type: STALE_DOC
    doc: discount-rules.md
    symbol: calculate_discount
    severity: HIGH
    reason: function body hash changed and documentation hash is old
```

## Docs Agent Task

```text
Task:
    title: Update discount rules documentation for VIP logic
    assignee_type: Docs Agent
    acceptance_criteria:
        - VIP discount behavior is documented.
        - linked symbol hash is updated.
        - Decision or product rule is referenced.
```

## Graph-Guided Code Generation Example

Later, a user asks:

```text
Add a function that previews the final discount before checkout.
```

Retrieval flow:

```text
1. Embed user request.
2. Vector search finds calculate_discount.
3. Graph expands to callers, docs, and related pricing decisions.
4. Context builder includes signature and documentation.
5. Model receives existing discount API instead of full source tree.
```

Prompt context includes:

```text
Existing function: calculate_discount(amount, user_type, is_vip)
Purpose: Computes final discount including VIP rule.
Related docs: discount-rules.md
Constraint: Do not duplicate discount logic; call existing function.
```

## Edge Cases

### Parser Cannot Resolve Call

CALLS relationship is stored with low confidence and excluded from high-risk automation.

### Documentation Missing

If `doc_required = true` and no doc exists, create MISSING_DOC finding.

### Generated Code Invents Unknown Function

If generated preview code calls `get_vip_discount_bonus` and graph does not contain it, validation rejects or requests repair.

## Developer Implementation Notes

- Hash changes should drive documentation generation.
- Bloom filter negative lookup can skip graph query for undocumented helper symbols.
- Graph retrieval weights must come from GraphRetrievalProfile.
- CI should block if the discount logic is revenue-critical and docs remain stale.
