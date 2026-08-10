---
doc_id: as.doc.stack.litellm-model-routing-profiles
title: 10 - Model Routing Profiles With LiteLLM
doc_type: standard
status: active
schema_version: '1.0'
owner: ai-platform-lead
summary: Specifies how ModelRoutingProfile maps task class and risk to LiteLLM model aliases,
  fallbacks, and offline stub behavior for Astloom services.
tags:
- litellm
- model-routing
- llm
- configuration
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/10-model-routing-profiles-with-litellm.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
- operators
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- docs/13-technology-stack-and-platform-decisions/09-litellm-llm-gateway.md
- docs/13-technology-stack-and-platform-decisions/12-litellm-environment-configuration.md
- docs/07-code-knowledge-graph/05-token-optimization-and-model-routing.md
- docs/10-gap-analysis/01-gap-register.md
- .env.example
doc_version: 1.0.1
audience:
- engineer
- architect
- operator
primary_entities:
- ModelRoutingProfile
- LiteLLMGateway
- LlmCompletionPort
relations_declared:
- type: depends_on
  target: docs/13-technology-stack-and-platform-decisions/09-litellm-llm-gateway.md
- type: complements
  target: docs/07-code-knowledge-graph/05-token-optimization-and-model-routing.md
chunk_hints:
  strategy: heading_h2
  max_tokens: 700
  overlap_tokens: 48
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 10 - Model Routing Profiles With LiteLLM

## Purpose

Defines how Astloom selects models **after** the LiteLLM gateway decision (`09-litellm-llm-gateway.md`). A `ModelRoutingProfile` answers *which* LiteLLM model alias to use; LiteLLM answers *how* to invoke it.

## Profile Fields

| Field | Meaning |
| --- | --- |
| `profile_id` | Stable id (tenant- or environment-scoped) |
| `task_class` | e.g. `docs.generate`, `rules.judge`, `codegen.synthesize`, `embed.symbol` |
| `risk_level` | `low` / `medium` / `high` |
| `primary_model` | LiteLLM model string (required) |
| `fallback_models` | Ordered LiteLLM aliases on primary failure |
| `max_tokens` | Hard cap for the task class |
| `timeout_ms` | Bound latency |
| `json_mode` | Required for judge / structured outputs |
| `allow_stub` | If true, services may use heuristic / `LocalEmbeddingStub` when no credentials |

## Default Task Mapping

Operators may override aliases via env (see `backend/packages/llm_gateway/README.md`).
Built-in resolver: `llm_gateway.resolve_route`.

**Published defaults (GAP-003 closed):**

| File | Environment | Role |
| --- | --- | --- |
| `backend/configs/model-routing/default.json` | `local` | Ollama LiteLLM aliases |
| `backend/configs/model-routing/cloud.json` | `cloud` | OpenAI / Anthropic aliases |
| `backend/configs/model-routing/model-routing-profile.schema.json` | — | JSON Schema |

Selection: `ASTLOOM_LITELLM_ROUTING_ENV=local|cloud` (default `local`), or
`ASTLOOM_LITELLM_ROUTING_PROFILE=/path/to/profile.json`.

| Task class | Env override | Notes |
| --- | --- | --- |
| `docs.generate` | `ASTLOOM_LITELLM_MODEL_DOCS` | Falls back to profile primary, then `ASTLOOM_LITELLM_DEFAULT_MODEL`; heuristic if empty / failure |
| `rules.judge` | `ASTLOOM_LITELLM_MODEL_JUDGE` | `json_mode=true` |
| `codegen.synthesize` | `ASTLOOM_LITELLM_MODEL_CODEGEN` | Higher max_tokens at medium/high risk |
| `embed.symbol` | `ASTLOOM_LITELLM_MODEL_EMBED` | Off by default (`ASTLOOM_LITELLM_EMBEDDINGS_ENABLED=false`); stub fallback |

Risk comes from `ASTLOOM_LITELLM_RISK_LEVEL` (`low` / `medium` / `high`). Fallbacks:
`ASTLOOM_LITELLM_FALLBACK_MODELS` (comma-separated) override profile fallbacks when set.

## Resolution Order

1. Project override profile (if present).
2. Tenant default profile.
3. Environment default profile.
4. Built-in safe defaults with `allow_stub=true` for offline/dev.

## Service Obligations

- Resolve profile before calling `LlmCompletionPort` / `LlmEmbeddingPort`.
- Pass the resolved LiteLLM model alias to the adapter — do not hard-code vendor model names in use cases.
- Emit observability: `profile_id`, `task_class`, `model`, tokens, latency, tenant, project.
- On exhaustion of fallbacks: follow policy (escalate, skip docs, or fail closed for high-risk judge).

## Out of Scope

- IDE or external agent-runtime model selection (outside Astloom process).
- Replacing pgvector storage.

## Related

- Gateway ADR: `09-litellm-llm-gateway.md`
- Token optimization: `../07-code-knowledge-graph/05-token-optimization-and-model-routing.md`
