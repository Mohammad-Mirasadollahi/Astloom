---
doc_id: as.doc.ckg.ingestion-and-living-documentation-workflow
title: Ingestion and Living Documentation Workflow
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This workflow updates the Code-Knowledge Graph whenever code changes. It parses code,
  detects changed symbols, generates or refreshes documentation for changed nodes, and upserts
  nodes and relationships into Neo4j.
tags:
- standard
- ckg
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/03-ingestion-and-living-documentation-workflow.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs
- backend/services/code-graph-service/src/code_graph_service/application/ingest/human_docs.py::HumanDocIngestMixin
- backend/services/code-graph-service/src/code_graph_service/domain/symbol_resolve.py::resolve_linked_symbol
- backend/services/code-graph-service/src/code_graph_service/domain/doc_discovery.py::discover_documentation_files
doc_version: 1.1.0
updated_at: '2026-09-03'
---

# Ingestion and Living Documentation Workflow

## Purpose

This workflow updates the Code-Knowledge Graph whenever code changes. It parses code, detects changed symbols, generates or refreshes documentation for changed nodes, and upserts nodes and relationships into Neo4j.

## Trigger Strategy

The system should not index on every file save by default. Save events are too noisy and often represent incomplete work.

Recommended triggers:

- Git commit.
- Pull request opened or updated.
- Manual sync button in an IDE / Astloom Client.
- Scheduled repository scan.
- CI indexing job.
- Explicit agent request after code generation.
- Optional batched pending-sync watcher (freshness banners; not per-keystroke indexing).

### Standards gate (Skip vs Ingest)

Before Phase 1/2 writes, Full-tier-nonconforming documentation paths may be
**skipped** for the run or **ingested** anyway. Interactive CLI can ask once;
scripts use `--skip-nonconforming` / `--sync-nonconforming`. For watcher flush
and Client-driven sync without a TTY, the durable choice lives in **Astloom
Client → Project settings → Sync → Nonconforming paths** and must be changeable
anytime. Normative contract: [`51-client-standards-gate-and-watcher-policy.md`](51-client-standards-gate-and-watcher-policy.md).

## Workflow Steps

### 1. Trigger

A repository event or manual sync starts the ingestion job. The job records repository path, commit hash, changed files, branch, actor, and correlation ID.

### 2. File Discovery

The system identifies supported source files and excludes generated files, vendor directories, build outputs, dependency folders, caches, and binary files.

For the `astloom sync` operator path, discovery is driven by a **required** filter file (`astloom.sync.yaml` / `.astloom/sync.yaml`) plus built-in language excludes and optional wildcards. See [42 - Astloom CLI Command Reference § Sync filters](../08-software-engineering-architecture/42-astloom-cli-command-reference.md#sync-filters) and `code_graph_service.domain.repo_discovery`.

### 3. Parsing (multi-language)

Python is the mandatory baseline language (`stdlib_ast`). TypeScript, JavaScript, Go, and Rust are supported through tree-sitter adapters registered in `code_graph_service.domain.parsers`.

Each file carries an explicit `language` (or is mapped from extension). Parsers emit a common `ParsedSymbol` schema without executing project code. Unsupported languages fail validation rather than writing incomplete nodes.


### 4. Symbol Extraction

The parser extracts code symbols and metadata:

- symbol kind,
- qualified name,
- signature,
- parameters,
- return type when available,
- body range,
- call expressions,
- imports,
- inheritance declarations.

### 5. Hash-Based Diffing

For every extracted symbol, the system computes a normalized hash and compares it to the hash stored in Neo4j.

Only changed or new symbols are sent to the AI documentation pipeline. Unchanged symbols are not reprocessed.

### 6. AI Documentation Generation

When living LLM docs are enabled (`ASTLOOM_LITELLM_DOCS_ENABLED`), each changed
**file** sends one batched Provider `complete` (`generate_many`) covering the
changed symbols in that file (JSON map, chunks of 16). This is not one call per
symbol. When docs are disabled, the heuristic generator fills stubs without RPM.

Generated documentation includes:

- purpose,
- parameters,
- return value,
- side effects,
- dependencies,
- error behavior,
- usage notes,
- risk notes when relevant.

After the file worker pool, one cross-file finalize pass relinks unresolved
`CALLS` (batched Neo4j deletes/puts). Content-push runs that pass only on the
last HTTP batch. Operator detail:
[`82`](82-sync-finalizing-and-provider-cost-runbook.md).

### 7. Embedding Generation

A compact semantic representation is embedded for vector search. The embedding should represent the symbol purpose and relationships, not just raw code text.

### 8. Graph Upsert

Neo4j is updated with new or changed nodes and relationships.

Upsert operations should be idempotent:

- merge Project node,
- merge File node,
- merge Class/Function/Method nodes,
- update hash and documentation,
- merge CONTAINS relationships,
- merge IMPORTS relationships,
- merge CALLS relationships,
- merge INHERITS_FROM relationships.

### 9. Drift and Impact Events

After graph update, the system emits events for Docs-as-Code and Orchestration:

- changed documented symbol,
- missing documentation,
- changed public API,
- changed dependency edge,
- changed call graph impact.

### 10. Human documentation Phase 2 (`astloom sync`)

After Phase 1 code ingest, `astloom sync` runs a second phase when `docs.match` is non-empty (default `**/*.md` / `**/*.mdx`):

1. Discover Markdown via `docs.match` wildcards and **docs-only** `docs.exclude` (`code_graph_service.domain.doc_discovery` — not the language matrix). Code excludes (`code.exclude`) do not apply to this phase.
2. **Order** the queue using the docs catalog cache when present (evidence citations and `lifecycle_lane: current` first). Catalog tags never create edges.
3. **Evidence merge (default):** extract path citations with the same rules as `docs-suggest-links`, merge into `linked_symbols`, and by default persist to YAML frontmatter (`ASTLOOM_SYNC_DOCS_EVIDENCE` / `ASTLOOM_SYNC_DOCS_EVIDENCE_APPLY`).
4. Index each document into **docs-sync-service** (SoT for Document / DocAnchor / Drift) with frontmatter (`linked_symbols` required for linking).
5. Resolve each `linked_symbols` token against the code graph (`qualified_name` or `file_path::SymbolName`). Unresolved tokens do **not** create edges.
6. Project human doc nodes into Neo4j as `doc:human:{project_id}:{doc_id}` (`kind=documentation`, `doc_status=human`) and merge `DOCUMENTED_BY` from each resolved code symbol → human doc (same direction as living AI docs).
7. Register docs-sync anchors for resolved links so drift can compare code hashes later.

Living AI docs (`doc:{project}:{qualified_name}`) remain separate from human projections. Body-tier Markdown without Full-tier frontmatter is still indexed in docs-sync via provisional fields, but receives no `DOCUMENTED_BY` edges until `linked_symbols` resolve.

### Hybrid coverage pack (agent read path)

`build_generation_context` merges layers for the seed symbol via
`code_graph_service.domain.hybrid_doc_coverage.build_symbol_doc_coverage`:

| Layer | Source | When missing |
| --- | --- | --- |
| AST | neighbors (`CALLS` / `IMPORTS` / …) | (always present after Phase 1 for ingested symbols) |
| Living | symbol `ai_documentation` + living `DOCUMENTED_BY` | fall back to AST |
| Human | `doc:human:…` via resolved `linked_symbols` | fall back to living |
| Rationale | `# WHY:` / `NOTE` / `HACK` nodes | optional enrichment |

Preference for prompt snippets: **human → living → rationale → AST**. No edges are invented on read.

Evidence-only link suggestions (write path): `astloom docs-suggest-links` proposes
`path::Symbol` tokens from Markdown path citations; `--apply` updates frontmatter only.
Phase 2 sync also merges evidence by default and remains the sole edge writer for resolved
tokens. Catalog: [`42-documentation-catalog-and-lane-cache.md`](./42-documentation-catalog-and-lane-cache.md).
Full normative hybrid detail: [`41-hybrid-documentation-coverage.md`](./41-hybrid-documentation-coverage.md).

Orchestration lives in `astloom_cli.docs_link_sync` (in-process clients; no cross-service DB reads). Disable Phase 2 with `docs.match: []` or `docs.enabled: false`.

## Pseudo-Code

```text
ingest_repository_change(change_event):
    files = discover_supported_files(change_event)
    for file in files:
        ast = parse_with_tree_sitter(file)
        symbols = extract_symbols(ast)
        imports = extract_imports(ast)
        calls = extract_calls(ast)

        upsert_file_node(file)

        for symbol in symbols:
            new_hash = normalized_ast_hash(symbol)
            old_hash = graph.get_hash(symbol.identity)

            if old_hash != new_hash:
                doc = generate_ai_documentation(symbol)
                embedding = embed(symbol, doc)
                upsert_symbol(symbol, new_hash, doc, embedding)
            else:
                touch_symbol_index_metadata(symbol)

        upsert_relationships(file, symbols, imports, calls)
        emit_graph_delta_events(file)
```

## Documentation Quality Rules

Generated documentation should not be vague. It must include concrete information available from code and graph context.

Bad documentation:

```text
This function handles user data.
```

Better documentation:

```text
Loads a user record by ID, validates that the record exists, and returns a normalized user DTO. It depends on UserRepository.findById and throws NotFoundError when the user does not exist.
```

## Failure Handling

- If parsing fails, store an indexing failure and do not delete existing graph data.
- If AI documentation fails, upsert the symbol with `doc_status = PENDING`.
- If embedding fails, keep graph structure and schedule embedding retry.
- If relationship resolution is uncertain, store relationship with low confidence.
- If graph upsert fails, retry idempotently using the same correlation ID.

## Parallel sync under RPM sessions

`astloom sync` / `ingest_repo` uses bounded file workers from
`ASTLOOM_SYNC_CPU_PERCENT` (preferred) or `ASTLOOM_SYNC_MAX_FILE_WORKERS`
(exact override). Default **auto**:

- LLM-cold (docs off and embeds not cloud): `min(cpu_count, ASTLOOM_LITELLM_RPM)`
- LLM-hot (living docs and/or cloud embeds): `min(cpu_count, ASTLOOM_LITELLM_RPM // 2)`

LiteLLM `complete`/`embed` calls are gated by tracked RPM sessions (start + end)
under `ASTLOOM_LITELLM_RPM`. Graph store access goes through `LockedStore`:
Postgres stays fully serialized; Neo4j uses a small concurrent Bolt budget
(`store_concurrency`). Observe sessions via `GET /api/v1/llm/sessions` or
`astloom llm sessions`.

Design pack: [`37`](37-rpm-session-parallel-sync-feature-specification.md) →
[`38`](38-rpm-session-parallel-sync-high-level-design.md) →
[`39`](39-rpm-session-parallel-sync-low-level-design.md) →
[`40`](40-rpm-session-parallel-sync-risks-challenges-and-acceptance.md) →
[`50`](50-sync-cpu-budget-and-store-concurrency-lld.md) (CPU percent + store concurrency) →
[`82`](82-sync-finalizing-and-provider-cost-runbook.md) (finalizing hang / Provider cost).
