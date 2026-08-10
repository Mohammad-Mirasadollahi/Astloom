---
doc_id: as.doc.codegraph.language-support-policy
title: 10 - Language Support Policy
doc_type: standard
status: active
schema_version: '1.0'
owner: code-graph-lead
summary: 'Normative language matrix for Code-Knowledge Graph ingestion: Python is required;
  TypeScript, JavaScript, Go, Rust, and Java are supported via tree-sitter adapters into a shared
  symbol schema.'
tags:
- code-graph
- parsers
- tree-sitter
- python
- rust
- java
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/10-language-support-policy.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/services/code-graph-service/src/code_graph_service/domain/languages.py::language_matrix
- backend/services/code-graph-service/src/code_graph_service/domain/parsers/__init__.py::parse_source
related_docs:
- as.doc.codegraph.neo4j-migration-plan
- docs/07-code-knowledge-graph/03-ingestion-and-living-documentation-workflow.md
- docs/07-code-knowledge-graph/48-ast-and-lsp-hybrid-parsing-adr.md
- as.doc.ckg.codebase-memory-language-breadth-and-speed
doc_version: 1.1.3
audience:
- engineer
- architect
- agent
primary_entities:
- LanguageMatrix
- ParserAdapter
- CodeSymbol
relations_declared:
- type: constrains
  target: backend/services/code-graph-service/
- type: complements
  target: docs/07-code-knowledge-graph/11-neo4j-migration-plan.md
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 10 - Language Support Policy

## Purpose

Defines which programming languages the Code-Knowledge Graph may ingest, which parsers own each language, and the non-negotiable Python baseline. All supported languages normalize into the same symbol/edge schema so retrieval and generation context remain language-agnostic at the Store port.

Durable ingest uses AST adapters only (stdlib `ast` / tree-sitter). Language Server Protocol is **not** a language-matrix mechanism and must not dual-write the durable graph; see `48-ast-and-lsp-hybrid-parsing-adr.md`.

## Mandatory Baseline: Python

**Python must remain supported.** It is the required baseline language for the Code-Knowledge Graph.

Rules:

- `LANGUAGE_MATRIX["python"].status` must remain `supported`.
- `LANGUAGE_MATRIX["python"].required` must remain `true`.
- Ingest, hashing, documentation refresh, graph edges, semantic ranking stubs, generation-context packs, and generated-code validation must work for `.py` sources.
- Default ingest language is `python` when callers omit `language`.
- Service startup calls `assert_required_languages_supported()` and fails fast if Python is not supported.
- Neo4j cutover and parser swaps must not regress Python support.

Current Python parser: stdlib `ast` (`parser=stdlib_ast`).

## Supported Languages

| Language   | Status    | Required | Parser        | Extensions                         |
|------------|-----------|----------|---------------|------------------------------------|
| Python     | supported | true     | stdlib_ast    | `.py`                              |
| TypeScript | supported | false    | tree_sitter   | `.ts`, `.tsx`, `.mts`, `.cts`      |
| JavaScript | supported | false    | tree_sitter   | `.js`, `.jsx`, `.mjs`, `.cjs`      |
| Go         | supported | false    | tree_sitter   | `.go`                              |
| Rust       | supported | false    | tree_sitter   | `.rs`                              |
| Java       | supported | false    | tree_sitter   | `.java`                            |

Unsupported languages return a validation error. Call resolution also captures `getattr(obj, "name")` string attributes as call refs (Codebase-Memory hybrid Wave D).

## Module Ownership

| Concern | Owner |
|---------|-------|
| Language matrix and guards | `code_graph_service.domain.languages` |
| Parser registry | `code_graph_service.domain.parsers` |
| Python adapter | `code_graph_service.domain.parsing` (`parse_python_source`) |
| JS/TS/Go/Rust/Java adapters | `code_graph_service.domain.parsers.{javascript,typescript,go_lang,rust_lang,java_lang}` |
| Ingest orchestration | `code_graph_service.application.service.CodeGraphService` |
| Cross-language resolution | `code_graph_service.domain.cross_language` |
| Package-manager aliases | `code_graph_service.domain.package_manifests` |
| Confidence caps | `code_graph_service.domain.confidence_policy` |
| DI injection bindings | `code_graph_service.domain.di_injections` (FastAPI Depends, Nest ctor/`@Inject`, Spring `@Autowired`/`@Inject`, Go Wire `wire.Build`) |

## Multi-Language Repository Behavior

- Ingest is **per file** and carries an explicit `language` field (or extension-based detection via `detect_language_from_path`).
- A polyglot repository may index each supported language independently into one project-scoped graph.
- Cross-language **CALLS** and **IMPORTS** resolve through `code_graph_service.domain.cross_language`:
  - same-language resolution first;
  - then normalized qualified names (`::` / `/` → `.`) and short-name indexes across the project;
  - import paths may resolve to another language's file via file-stem matching (for example `./helpers` → `helpers.py`);
  - edges that remain `unresolved:*` are relinked on later ingest when a unique target appears.
- Package-manager aliases (`domain/package_manifests.py`) rewrite imports using:
  - `pyproject.toml` project name;
  - `go.mod` module + `replace` directives;
  - `Cargo.toml` package name + `path` dependencies;
  - `package.json` name, `imports`, and local `file:` / `workspace:` deps;
  - `tsconfig.json` `compilerOptions.paths` (root + one-level nested).
- Confidence caps (`domain/confidence_policy.py`): cross-language and package/DI heuristics never claim `exact`; reflection/monkeypatch cap at `ambiguous`; `runtime_trace` boosts (see `15-call-graph-confidence-and-runtime-traces.md`).
- Framework DI bindings (`domain/di_injections.py`) emit `CALLS` with `provenance=di_injection` for FastAPI `Depends(...)` and Nest/TS constructor type / `@Inject` patterns.
- Edge metadata may include `cross_language`, `source_language`, `target_language`, `relinked`, `resolved_via`, and `provenance`.
- Ambiguous cross-language matches stay `AMBIGUOUS` (multiple candidate edges) rather than inventing a single target.
- The service derives a **polyglot project profile** (`get_polyglot_profile` / `GET .../graph/language-profile`) that states:
  - which languages are present;
  - whether they are isolated or connected through cross-language CALLS/IMPORTS;
  - related language clusters (connected components);
  - a human/agent-readable `summary`.
- Generation-context packs include the polyglot summary so agents know languages are related.

## Acceptance Criteria

- Python ingest golden path remains green.
- TypeScript, JavaScript, Go, and Rust each extract at least functions/methods (and classes/structs/traits where applicable), imports, and call names into `ParsedSymbol`.
- `supported_languages()` returns all five languages above.
- `required_languages()` returns only `python`.
- Hash normalization is language-aware (`#` vs `//` / block comments).
- A Python caller can form a `CALLS` edge to a uniquely named Rust/Go/JS/TS symbol in the same project (confidence `probable`, `cross_language=true`).
- An unresolved call is relinked after the target language file is ingested later.
- For a Python+Rust related pair, `language-profile` reports `is_polyglot=true`, `relatedness=polyglot_fully_related` (or partially when more languages are isolated), and non-empty `language_links`.
- `Cargo.toml` / `tsconfig` paths / `go.mod replace` aliases participate in IMPORT rewrite tests.
- FastAPI `Depends` ingest emits at least one `CALLS` edge with `provenance=di_injection` at `probable` confidence.

## Implementation References

- Matrix: `backend/services/code-graph-service/src/code_graph_service/domain/languages.py`
- Registry: `backend/services/code-graph-service/src/code_graph_service/domain/parsers/__init__.py`
- Contract: `backend/services/code-graph-service/docs/phase-7-api-contract.md`
- Migration: `11-neo4j-migration-plan.md`
- AST vs optional LSP: `48-ast-and-lsp-hybrid-parsing-adr.md`
- Upstream CBM language breadth / speed (ideas only): `52-codebase-memory-language-breadth-and-indexing-speed.md`
