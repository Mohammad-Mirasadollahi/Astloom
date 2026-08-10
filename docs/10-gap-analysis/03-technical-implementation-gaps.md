---
doc_id: as.doc.gap.technical-implementation-gaps
title: Technical Implementation Gaps
doc_type: gap
status: draft
schema_version: '1.0'
owner: platform-docs
summary: Technical implementation gaps GAP-T01–T08 are CLOSED with on-disk evidence
  (hashing, call-graph, embeddings/TurboVec, ContextBundle audit, LLM judge, SDK harness,
  port preflight, fixture catalog).
tags:
- gap
- gap
phase: 10-gap-analysis
canonical_path: docs/10-gap-analysis/03-technical-implementation-gaps.md
lifecycle_lane: future
concern_lane: gap
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols:
- backend/services/code-graph-service/src/code_graph_service/domain/runtime_traces.py::ObservedCall
- tests/backend/services/code-graph-service/test_call_graph_corpus_accuracy.py::test_call_graph_corpus_accuracy_gate
- backend/services/code-graph-service/src/code_graph_service/application/embedding_refresh.py::EmbeddingRefreshMixin
- backend/services/code-graph-service/src/code_graph_service/application/embedding_refresh.py::RefreshReport
- backend/services/memory-service/src/memory_service/domain/embeddings_store.py::MemoryEmbeddingRow
- backend/services/memory-service/src/memory_service/domain/embeddings_store.py::stage1_retrieve
- tests/backend/services/code-graph-service/test_embedding_refresh.py::test_refresh_embeddings_indexes_missing_rows
- tests/backend/services/code-graph-service/test_embedding_refresh.py::helper
- tests/backend/services/memory-service/test_memory_embeddings.py::test_retrieve_by_embedding_returns_indexed_memory
- backend/services/memory-service/src/memory_service/domain/bundle_verifier.py::VerificationFinding
- tests/backend/services/memory-service/test_context_bundle_verifier.py::test_verify_fresh_bundle_passes_schema_and_checks
- tests/backend/services/memory-service/test_context_bundle_verifier.py::memory
- backend/services/rule-engine-service/src/rule_engine_service/bootstrap.py::Settings
- backend/services/rule-engine-service/src/rule_engine_service/litellm_judge.py::LiteLLMJudge
- tests/backend/services/rule-engine-service/test_litellm_judge.py::test_litellm_judge_parses_structured_verdict_and_replay
- backend/tools/sdk-generation/generate.py::extract_operations
- backend/packages/adapter_harness/capability.py::declare_capabilities
- tests/backend/packages/test_adapter_harness.py::test_declare_and_validate_capabilities
- backend/packages/port_profile/loader.py::PortProfileError
- backend/packages/astloom_cli/commands/ports.py::cmd_ports_show
- backend/packages/astloom_cli/service_runtime/lifecycle.py::service_state
- tests/backend/tools/astloom-cli/test_astloom_cli.py::test_profile_list_and_show
- tests/support/synthetic_workflow.py::generate_workflow
- tests/support/synthetic_workflow.py::SyntheticScope
- tests/backend/fixtures/test_fixture_catalog.py::test_catalog_schema_and_policy
doc_version: 1.2.4
updated_at: 2026-08-10
---

# Technical Implementation Gaps

## Purpose

This document captures technical implementation gaps that require deeper design, prototyping, benchmarking, or proof-of-concept work.

## GAP-T01 - AST Hash Stability

The design depends on normalized AST hashes, but normalization rules need language-specific validation.

Questions:

- Which syntax changes should not change the hash?
- Which comments should affect the hash because they contain doc flags?
- How are generated files handled?
- How does parser version affect hash stability?

Resolution output:

- Hash normalization spec per language.
- Regression test corpus.

**Status: CLOSED**

Closed in:

- `docs/07-code-knowledge-graph/14-ast-hash-stability-contract.md`
- `code_graph_service/domain/hashing.py` (`content_hash`, `HASH_VERSION`, astloom flags)
- `tests/backend/services/code-graph-service/hash_corpus/` + `test_hash_corpus.py`

## GAP-T02 - Call Graph Accuracy

Call graph extraction can be inaccurate in dynamic languages.

Questions:

- How are dynamic dispatch, reflection, dependency injection, and monkey patching handled?
- What confidence level is required for impact analysis?
- When should runtime traces supplement static parsing?

Resolution output:

- Call resolution confidence model.
- Static plus runtime hybrid strategy.

**Status: CLOSED**

Closed in:

- `docs/07-code-knowledge-graph/15-call-graph-confidence-and-runtime-traces.md`
- `backend/services/code-graph-service/src/code_graph_service/domain/runtime_traces.py`
- `tests/backend/services/code-graph-service/call_graph_corpus/`
- `tests/backend/services/code-graph-service/test_call_graph_corpus_accuracy.py`

## GAP-T03 - Embedding Storage and Refresh Policy

Embeddings are needed for retrieval, but refresh and invalidation strategy needs definition.

Questions:

- When should embeddings regenerate?
- Are embeddings stored in Neo4j or external vector store?
- How are old embeddings invalidated?
- How are embedding model changes handled?

**Status: CLOSED**

Closed in:

- `docs/13-technology-stack-and-platform-decisions/14-embedding-lifecycle-and-refresh.md`
- `backend/configs/embeddings/refresh-policy.json` (`vector(1024)` SoR)
- `backend/services/code-graph-service/src/code_graph_service/application/embedding_refresh.py`
- `backend/services/memory-service/src/memory_service/domain/embeddings_store.py`
- `backend/services/memory-service/migrations/0003_memory_embeddings.sql`
- `tests/backend/services/code-graph-service/test_embedding_refresh.py`
- `tests/backend/services/memory-service/test_memory_embeddings.py`

Notes: Stage-1 hybrid RAG remains kind-filtered pgvector before optional TurboVec Stage-2; durable dims are `vector(1024)`.

## GAP-T04 - Prompt Context Verification

ContextBundles should be source-referenced, but verification logic needs more detail.

Questions:

- How does the system prove a ContextBundle included current state?
- How are omitted high-scoring memory items explained?
- How is prompt safety tested?

**Status: CLOSED**

Closed in:

- `docs/02-memory-and-context/13-context-bundle-audit-and-verification.md`
- `backend/configs/schemas/context-bundle-audit.schema.json`
- `backend/services/memory-service/src/memory_service/domain/bundle_verifier.py`
- `tests/backend/services/memory-service/test_context_bundle_verifier.py`

## GAP-T05 - LLM Judge Determinism

LLM-as-a-Judge is useful but can be inconsistent.

Questions:

- Which policies are eligible for LLM judgment?
- What temperature and output constraints are required?
- How are verdicts reproduced later?
- How are low-confidence verdicts handled?

**Status: CLOSED**

Closed in:

- `docs/04-rule-engine-orchestration/11-llm-judge-operating-standard.md`
- `backend/configs/schemas/llm-judge-verdict.schema.json`
- `backend/services/rule-engine-service/src/rule_engine_service/litellm_judge.py`
- `backend/services/rule-engine-service/src/rule_engine_service/bootstrap.py` (`ASTLOOM_RULE_JUDGE=litellm|heuristic`)
- `tests/backend/services/rule-engine-service/test_litellm_judge.py`

## GAP-T06 - SDK Language, Packaging, And Adapter Harness Finalization

Astloom now defines the SDK platform and SDK engineering architecture, but the final implementation plan still needs language prioritization, package publishing policy, and adapter harness details.

Questions:

- Which SDK packages ship first: TypeScript, Python, or both in the same milestone?
- Which package registries and naming conventions are used?
- Which generator stack owns OpenAPI, event schema, and config schema outputs?
- How are adapter capabilities declared and validated in the first implementation?
- How are adapter contract tests run locally and in CI?
- How are adapter secrets referenced without exposing secret values?

**Status: CLOSED**

Closed in:

- `docs/05-interoperability-ecosystem/11-sdk-release-and-adapter-harness.md`
- `backend/packages/astloom_sdk/`
- `backend/packages/sdk/typescript/src/client.ts`
- `backend/tools/sdk-generation/generate.py` + `backend/packages/sdk/generated/`
- `backend/packages/adapter_harness/`
- `tests/backend/packages/test_adapter_harness.py`
- `pyproject.toml` packages list (`astloom_sdk`, `adapter_harness`)

## GAP-T07 - Port Preflight Tool

Port management is documented, but the actual preflight mechanism needs design.

Questions:

- Is port preflight a CLI command, startup library, or script?
- How does it detect owning process cross-platform?
- How does it write resolved port maps?
- How does it integrate with Docker Compose or local orchestration?

Resolution output:

- Port preflight tool spec.
- Local development startup flow.

**Status: CLOSED**

Closed in:

- `docs/08-software-engineering-architecture/04-development-port-management.md`
- `backend/packages/port_profile/loader.py` (`find_port_owner`, `suggest_alternate_port`, `run_preflight`, `write_port_map`)
- `backend/packages/astloom_cli/commands/ports.py` (`astloom ports check`)
- `backend/packages/astloom_cli/service_runtime/lifecycle.py` (service start preflight)
- `scripts/install/common.sh` (`run_port_preflight`) + stage 04 Compose gate
- `tests/backend/tools/astloom-cli/test_astloom_cli.py` (occupied-port + ss owner regression)
- `tests/backend/gates/port-profile-verification/`

## GAP-T08 - Test Data and Fixture Strategy

The platform needs realistic test data for graph, memory, rules, broker, and docs drift.

Questions:

- What sample repositories are used?
- How are synthetic agents simulated?
- How are security-sensitive fixtures handled?
- How is multi-tenant isolation tested?

**Status: CLOSED**

Closed in:

- `docs/08-software-engineering-architecture/51-test-fixture-catalog.md`
- `tests/backend/fixtures/catalog.json`
- `tests/backend/fixtures/sample_repos/`
- `tests/backend/fixtures/multi_tenant/`
- `tests/support/synthetic_workflow.py`
- `tests/backend/fixtures/test_fixture_catalog.py`
