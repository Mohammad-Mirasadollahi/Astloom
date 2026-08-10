---
doc_id: as.doc.ckg.graph-guided-code-generation-workflow
title: Graph-Guided Code Generation Workflow
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Graph-guided code generation lets AI write new code using real project context from
  the Code-Knowledge Graph. Instead of sending the full repository to the model, the system
  retrieves relevant symbols, signatures, documentation, and relationships.
tags:
- standard
- ckg
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/04-graph-guided-code-generation-workflow.md
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

# Graph-Guided Code Generation Workflow

## Purpose

Graph-guided code generation lets AI write new code using real project context from the Code-Knowledge Graph. Instead of sending the full repository to the model, the system retrieves relevant symbols, signatures, documentation, and relationships.

## Workflow Steps

### 1. User Request

The user asks for new code or a change. Example:

```text
Write a function that loads users using the existing database utilities.
```

### 2. Request Understanding

The system extracts intent, target domain, likely entities, required operations, and risk level.

Extracted intent example:

```text
intent: create_function
domain: user_data
operation: load_users
dependencies_needed: database utilities, user repository, DTO conventions
```

### 3. Vector Search

The request is embedded and searched against graph node embeddings. Candidate nodes may include functions, classes, files, and documentation nodes related to users and database access.

### 4. Graph Expansion

The top vector hits are expanded through graph relationships.

Expansion may include:

- functions called by the candidate node,
- callers of the candidate node,
- files that contain related functions,
- classes that own related methods,
- imports required by related files,
- documentation linked to related symbols,
- decisions or rules linked through Astloom.

### 5. Context Selection

The system selects compact context instead of raw full files.

Recommended context items:

- function signatures,
- short AI documentation,
- parameter and return type summaries,
- call relationships,
- import hints,
- relevant code snippets only when necessary,
- domain rules and active Decisions.

### 6. Prompt Construction

The prompt should be structured, not a large blob.

Prompt sections:

1. Task instruction.
2. Current architectural rules.
3. Relevant graph nodes.
4. Existing signatures and imports.
5. Constraints and acceptance criteria.
6. Output format requirement.

### 7. Code Generation

The model generates code using existing functions and project conventions. For complex generation, a stronger cloud model can be used. For simple documentation or small helper code, a local or cheaper model should be used.

### 8. Validation

Generated code should be validated through:

- static checks,
- import resolution,
- type checks when available,
- tests,
- graph consistency checks,
- policy checks for high-risk domains.

### 9. Graph Update

If generated code is accepted, the ingestion workflow updates the graph with new symbols, relationships, documentation, hashes, and embeddings.

## Retrieval Algorithm

```text
build_generation_context(user_request):
    request_embedding = embed(user_request)
    vector_hits = graph.vector_search(request_embedding, top_k=20)
    expanded = graph.expand(vector_hits, relationships=[CALLS, IMPORTS, CONTAINS, INHERITS_FROM])
    ranked = rank_by_relevance_authority_and_distance(expanded)
    compact = summarize_for_prompt(ranked, token_budget)
    return compact
```

## Anti-Hallucination Rules

The model should be instructed to:

- use only listed existing functions unless it explicitly creates a new one,
- preserve existing naming conventions,
- import only known modules unless asked otherwise,
- mention missing dependencies instead of inventing them,
- respect active Decisions and Rules,
- produce code that can be re-indexed into the graph.

## Context Ranking Signals

Ranking should consider:

- semantic similarity to request,
- graph distance from top vector hits,
- symbol visibility,
- documentation freshness,
- call frequency,
- ownership authority,
- active Decision links,
- recent successful usage.

## Failure Handling

- If no graph context is found, ask for clarification or fall back to repository search.
- If graph context conflicts, surface the conflict before generating code.
- If required existing function is undocumented, retrieve signature and callers.
- If generated code references unknown symbols, reject or repair before proposing final output.
- If risk policy triggers, route through Astloom escalation before merge.
