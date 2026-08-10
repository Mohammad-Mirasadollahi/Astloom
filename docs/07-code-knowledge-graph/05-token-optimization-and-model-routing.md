---
doc_id: as.doc.ckg.token-optimization-and-model-routing
title: Token Optimization and Model Routing
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: The Code-Knowledge Graph must reduce LLM cost while improving output quality. It
  does this by avoiding full-repository prompting, processing only changed symbols, routing
  tasks to the cheapest capable model, and using graph summaries instead of raw code where
  possible.
tags:
- standard
- ckg
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/05-token-optimization-and-model-routing.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.ckg.headroom-native-context-compression
doc_version: 1.1.1
updated_at: 2026-08-10
---

# Token Optimization and Model Routing

## Purpose

The Code-Knowledge Graph must reduce LLM cost while improving output quality. It does this by avoiding full-repository prompting, processing only changed symbols, routing tasks to the cheapest capable model, and using graph summaries instead of raw code where possible.

**Native context compression** for bulky tool/RAG/JSON payloads is a separate Astloom product obligation (inspired by Headroom, Apache 2.0) — see [`54-headroom-native-context-compression.md`](54-headroom-native-context-compression.md). That lane runs inside Astloom before LiteLLM; it does not replace hash-diff or graph packs.

### Shipped surfaces (verify)

| Surface | How to use |
| --- | --- |
| MCP | `astloom_context_compress` / `retrieve` / `stats` (`programming-cursor-mcp` ≥ 1.3.1) |
| LiteLLM | Auto on long message contents; `ASTLOOM_CONTEXT_COMPRESS=0` disables |
| CLI | `astloom context measure --file …` · `astloom context stats` |
| Change-scoped export | `astloom pack review` (secret scan + token budget; see [`53`](53-repomix-prior-art-ideas-and-license.md)) |
| Explore packs | Response includes `estimated_tokens` (`chars÷4`) |

## LLM Gateway (normative)

All Astloom-initiated model calls for documentation, classification, judge-style structured outputs, and provider-backed embeddings **must** use **LiteLLM** via an application port. Do not call vendor SDKs directly from services.

- Stack ADR: `../13-technology-stack-and-platform-decisions/09-litellm-llm-gateway.md`
- Product-per-role: `../13-technology-stack-and-platform-decisions/07-service-product-standard.md`

`ModelRoutingProfile` selects LiteLLM model aliases (local or cloud). Offline Phase slices may keep heuristic docs / `LocalEmbeddingStub` until a profile enables live models.

## Strategy 1 - Hash-Based Diffing

Every function, method, class, and file receives a normalized hash. On each ingestion run, the system compares the new hash with the stored hash.

Only changed nodes are processed by AI documentation and embedding generation.

Benefits:

- fewer model calls,
- faster ingestion,
- lower cost,
- less repeated documentation churn.

## Strategy 2 - Smart Triggers

Documentation generation should not run on every file save by default. The system should prefer meaningful triggers.

Recommended triggers:

- commit,
- pull request update,
- manual sync,
- CI workflow,
- scheduled scan,
- accepted generated code.

This prevents expensive processing of temporary or unfinished code.

## Strategy 3 - Tiered LLM Routing

Different tasks require different model quality. Routing is expressed as LiteLLM model aliases in `ModelRoutingProfile` and executed through the LiteLLM gateway.

### Local or Low-Cost Models

Use for:

- function documentation,
- simple summaries,
- classification,
- low-risk extraction,
- embedding text preparation.

Examples (LiteLLM model strings — illustrative):

- `ollama/qwen2.5-coder` or other local OpenAI-compatible endpoints via LiteLLM,
- low-cost cloud aliases configured in LiteLLM.

### Strong Cloud Models

Use for:

- complex code generation,
- multi-file architectural changes,
- ambiguous reasoning,
- high-risk refactoring,
- final synthesis from graph context.

## Strategy 4 - Hierarchical Summarization

The model should not receive full code unless necessary. Context should be hierarchical:

1. project summary,
2. file summary,
3. class summary,
4. function signature,
5. function documentation,
6. code snippet only when needed.

For most generation tasks, signatures plus documentation plus graph relationships are enough.

## Strategy 4b - Structural-First Then Escalate

Coding agents **must** prefer cheap structural MCP tools before wide repository
reads (Codebase-Memory hybrid — docs `44`–`46`):

1. `astloom_code_graph_callers` / directed `impact` / `community` / `neighbors`
2. `astloom_code_graph_explore` or `hybrid_search` when the question is semantic
   or structural results are sparse
3. Raw file Read/Grep only under a remaining budget

Structural payloads include an `escalate_hint` so agents know the next tool.
Do not default to dumping full source into the prompt.

## Strategy 5 - Cheap Embeddings

Embeddings are used to find relevant graph nodes. They should be generated from compact semantic text rather than full raw source code.

Embedding input example:

```text
qualified_name: users.repository.findUserById
signature: findUserById(userId: string): Promise<User>
description: Loads a user by ID from the user repository.
relationships: calls db.query, used by auth.login
```

This improves retrieval and reduces embedding cost.

## Strategy 6 - Context Budgeting

Every generation request should have a token budget.

Suggested budget allocation:

- 20 percent task instruction and constraints,
- 25 percent current rules and Decisions,
- 30 percent graph context,
- 15 percent selected code snippets,
- 10 percent safety margin.

## Strategy 7 - Cacheable Graph Summaries

Stable graph summaries can be cached:

- project architecture summary,
- module summaries,
- stable API summaries,
- common domain glossary,
- active high-level Decisions.

These summaries should only invalidate when underlying graph hashes change.

## Routing Decision Logic

```text
if task == documentation_generation and risk <= medium:
    use local_or_low_cost_model
elif task == embedding_text_preparation:
    use local_or_low_cost_model
elif task == code_generation and complexity <= low:
    use low_cost_cloud_or_local_model
elif task == code_generation and complexity >= medium:
    use stronger_model
elif task touches security, billing, auth, or production:
    use stronger_model plus policy evaluation
```

## Cost Failure Modes

The system should detect and prevent:

- repeated documentation generation for unchanged code,
- full file prompts when summaries are enough,
- embedding full raw repositories,
- using strong models for simple documentation,
- invalidating cached context too often,
- generating docs for temporary code on every save.
