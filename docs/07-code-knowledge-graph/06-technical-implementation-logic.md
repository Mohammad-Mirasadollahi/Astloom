---
doc_id: as.doc.ckg.technical-implementation-logic
title: Code-Knowledge Graph - Technical Implementation Logic
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the implementation logic for a Neo4j-backed Code-Knowledge
  Graph with pgvector-backed semantic retrieval that supports live documentation and graph-guided
  code generation.
tags:
- standard
- ckg
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/06-technical-implementation-logic.md
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

# Code-Knowledge Graph - Technical Implementation Logic


## Purpose

This document defines the implementation logic for a Neo4j-backed Code-Knowledge Graph with pgvector-backed semantic retrieval that supports live documentation and graph-guided code generation.

## Technical Goal

This document defines the implementation logic for a Neo4j-backed Code-Knowledge Graph with pgvector-backed semantic retrieval that supports live documentation and graph-guided code generation.

## Core Services

### Repository Scanner

Discovers files, filters ignored paths, detects language, and emits file indexing jobs.

### AST Parser Service

Python is the **required** baseline language (`stdlib_ast`). TypeScript, JavaScript, Go, and Rust use tree-sitter adapters behind `parse_source(language, file_path, source)` and normalize into the shared symbol schema.


### Symbol Normalizer

Converts language-specific AST output into a common schema for File, Class, Function, Method, and Import nodes.

### Hash Service

Computes normalized AST hashes for files and symbols.

### Documentation Generator

Generates AI documentation for changed symbols only.

### Embedding Service

Creates compact semantic embeddings for search.

### Graph Upsert Service

Writes nodes and relationships to Neo4j using idempotent merge operations.

### Retrieval Service

Performs pgvector semantic search, Neo4j graph expansion, ranking, and prompt context construction.

## Ingestion Pseudo-Code

```text
run_ingestion(project, revision):
    changed_files = repository_scanner.discover(project, revision)

    for file in changed_files:
        if should_skip(file):
            continue

        ast = parser.parse(file)
        normalized = normalizer.extract(ast)

        file_hash = hash_service.hash_file(file)
        graph.merge_file(file, file_hash)

        for symbol in normalized.symbols:
            symbol_hash = hash_service.hash_symbol(symbol)
            previous = graph.get_symbol(symbol.identity)

            if previous is None:
                doc = doc_generator.generate(symbol)
                embedding_ref = embedding_service.embed_to_pgvector(symbol, doc)
                graph.create_symbol(symbol, symbol_hash, doc, embedding_ref)
            elif previous.hash_value != symbol_hash:
                doc = doc_generator.generate(symbol)
                embedding_ref = embedding_service.embed_to_pgvector(symbol, doc)
                graph.update_symbol(symbol, symbol_hash, doc, embedding_ref)
            else:
                graph.touch_symbol(symbol.identity)

        graph.replace_file_relationships(file, normalized.relationships)
        publish_graph_delta(file, normalized)
```

## Neo4j Upsert Pattern

Use stable IDs and MERGE patterns.

Example conceptual Cypher:

```text
MERGE (f:File {project_id: $project_id, path: $path})
SET f.content_hash = $content_hash,
    f.language = $language,
    f.last_indexed_at = $now

MERGE (fn:Function {function_id: $function_id})
SET fn.qualified_name = $qualified_name,
    fn.signature = $signature,
    fn.hash_value = $hash_value,
    fn.ai_documentation = $ai_documentation,
    fn.embedding_ref = $embedding_ref

MERGE (f)-[:CONTAINS]->(fn)
```

Relationship replacement should be scoped to the file revision so removed calls or imports do not remain active forever.

## Call Resolution Logic

Call resolution is not always exact in dynamic languages. Store confidence.

Resolution levels:

- `EXACT`: target symbol resolved unambiguously.
- `PROBABLE`: target resolved by import and name matching.
- `AMBIGUOUS`: multiple possible targets.
- `UNRESOLVED`: target not found.

High-risk automation should use only exact or verified probable relationships.

## Embedding Retrieval Logic

```text
retrieve_graph_context(request):
    request_vector = embed(request.text)
    candidates = pgvector.search(request_vector, top_k=K)
    expanded = expand_graph(candidates, max_depth=2)
    ranked = rank(candidates + expanded)
    compact_context = build_context_pack(ranked, token_budget)
    return compact_context
```

## Ranking Formula

```text
rank_score =
    vector_similarity * 0.35 +
    graph_proximity * 0.20 +
    doc_freshness * 0.15 +
    symbol_authority * 0.10 +
    call_frequency * 0.10 +
    decision_relevance * 0.10
```

Penalty factors:

- stale documentation,
- unresolved call edges,
- deprecated symbol,
- low-confidence parse result,
- restricted access.

## Documentation Generation Logic

Documentation should be generated from:

- normalized symbol signature,
- symbol body snippet,
- nearby class or module context,
- direct call targets,
- imported dependencies,
- existing doc if updating,
- active Decisions or Rules when linked.

Output must include:

- purpose,
- parameters,
- return value,
- side effects,
- dependencies,
- error behavior,
- usage notes,
- confidence or unknowns.

## Graph-Guided Code Generation Logic

```text
generate_code(request):
    context = retrieval_service.retrieve_graph_context(request)
    validate_context(context)
    prompt = build_structured_generation_prompt(request, context)
    draft = model.generate(prompt)
    validation = validate_generated_code(draft, context)

    if validation.has_unknown_symbols:
        repair_or_reject(draft, validation)

    if validation.high_risk:
        create_escalation_ticket(draft, validation)

    return draft_with_evidence_refs
```

## Integration with Astloom

The Code-Knowledge Graph should integrate with existing Astloom concepts:

- CodeSymbol maps to Function, Method, Class, and File graph nodes.
- AI documentation can link to Docs-as-Code Doc records.
- Hash changes can create DriftFindings.
- Graph deltas can create Activities.
- Generated code can create Tasks and WorkLogs.
- High-risk generated code must pass Rule Engine evaluation.
- Graph context can feed ContextBundles.

## Failure Handling

### Parser Failure

Store `index_status = PARSE_FAILED` on the File node and keep previous known-good graph relationships active until verified replacement is available.

### Documentation Failure

Set `doc_status = PENDING` and schedule retry. Do not block graph structure update unless documentation is required by policy.

### Embedding Failure

Store the node without embedding and mark `embedding_status = PENDING`. Retrieval can still use graph traversal and text search.

### Neo4j Write Failure

Retry using idempotency keys. If the failure persists, do not mark ingestion complete.

### Model Hallucination in Generated Code

Reject generated code that references symbols not found in the graph unless those symbols are explicitly created in the generated patch.

## Technical Acceptance Criteria

- A changed function is detected by hash comparison.
- Only changed functions are sent to documentation generation.
- Neo4j contains File, Function, Class, Method, CONTAINS, CALLS, IMPORTS, and INHERITS_FROM records.
- Vector search can retrieve relevant symbols for a natural-language request.
- Generated code prompt includes signatures and documentation instead of full repository source.
- Stale documentation creates a drift signal.
- Unknown generated symbol references are detected before acceptance.

## Configurable Graph Retrieval Weights

Graph retrieval weights must also be profile-driven. The ranking formula in this document is an example of feature composition, not a hard-coded implementation requirement.

The graph retrieval service should load a GraphRetrievalProfile based on tenant, repository, task type, and risk level.

Profile fields:

```text
GraphRetrievalProfile:
    profile_id
    tenant_id
    repository_id
    task_type
    risk_level
    version
    feature_weights
    expansion_limits
    confidence_thresholds
    status
```

Configurable features:

- vector similarity,
- graph proximity,
- documentation freshness,
- symbol authority,
- call frequency,
- active Decision relevance,
- parser confidence,
- owner verification,
- recent successful generation usage,
- incident relevance,
- stale documentation penalty,
- unresolved relationship penalty.

## Non-Hardcoded Ranking Flow

```text
rank_graph_node(node, request, profile):
    features = extract_graph_features(node, request)
    score = 0
    for name, value in features:
        score += normalize(value) * profile.feature_weights[name]
    score -= configured_penalties(node, profile)
    score += configured_boosts(node, request, profile)
    return score
```

The platform may ship default profiles, but production deployments must be able to tune them without code changes. Security-sensitive repositories may prioritize owner verification and active Decisions. Documentation generation may prioritize doc freshness and parser confidence. Code generation may prioritize graph proximity, symbol authority, and successful prior usage.

## Forgotten Code Context

Some code nodes may become low-visibility because they are rarely called or poorly linked, but they may still be important. The graph should not drop them only because they have low call frequency.

Low-visibility code nodes should be classified as:

- obsolete if the file or symbol is gone,
- dormant but important if linked to security, migration, incident, compliance, or recovery logic,
- under-linked if parser confidence is low or relationships are missing,
- low-priority if they are active but rarely relevant.

Each classification should determine retrieval behavior and maintenance tasks.


## Metadata-First Retrieval Extension

Astloom should use the Code-Knowledge Graph as a metadata-first retrieval layer. The retrieval service should first inspect FileMetadata, SymbolMetadata, DependencyMetadata, TestMetadata, documentation links, graph relationships, freshness, and confidence before reading full source code.

The source-read decision must be explicit. Metadata is enough for locating code, planning, impact analysis, documentation outlines, test discovery, and low-risk classification. Source must be read for logic modification, high-risk domains, stale metadata, low confidence, ambiguous call resolution, failing tests, or exact behavior questions.

Metadata-first retrieval should produce a ContextPack containing selected metadata records, score breakdowns, risk tags, freshness state, confidence, source-read recommendations, and evidence references. This ContextPack becomes the first code context passed to agents.

See:

- `07-metadata-first-code-understanding.md`
- `08-code-metadata-schema-and-lifecycle.md`
- `09-context-pack-retrieval-and-agent-workflow.md`
