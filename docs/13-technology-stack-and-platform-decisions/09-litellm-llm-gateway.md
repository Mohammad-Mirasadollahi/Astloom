---
doc_id: as.doc.stack.litellm-llm-gateway
title: 09 - LiteLLM LLM Gateway
doc_type: adr
status: active
schema_version: '1.0'
owner: platform-architecture
summary: Accepts LiteLLM as the sole approved LLM gateway for Astloom model completion,
  chat, and embedding-provider calls. Domain ports stay provider agnostic; infrastructure
  adapters must call LiteLLM, not vendor SDKs directly.
tags:
- litellm
- llm
- gateway
- model-routing
- adr
- adapter
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/09-litellm-llm-gateway.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- docs/13-technology-stack-and-platform-decisions/03-backend-api-and-service-stack.md
- docs/13-technology-stack-and-platform-decisions/07-service-product-standard.md
- docs/13-technology-stack-and-platform-decisions/10-model-routing-profiles-with-litellm.md
- docs/13-technology-stack-and-platform-decisions/12-litellm-environment-configuration.md
- docs/07-code-knowledge-graph/05-token-optimization-and-model-routing.md
- docs/07-code-knowledge-graph/37-rpm-session-parallel-sync-feature-specification.md
- docs/10-gap-analysis/01-gap-register.md
- .env.example
doc_version: 1.0.1
audience:
- engineer
- architect
- operator
- agent
primary_entities:
- LiteLLMGateway
- ModelRoutingProfile
- LlmCompletionPort
relations_declared:
- type: constrains
  target: backend/services/
- type: complements
  target: docs/07-code-knowledge-graph/05-token-optimization-and-model-routing.md
- type: resolves
  target: GAP-003
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
external_refs:
- https://docs.litellm.ai/
- https://github.com/BerriAI/litellm
updated_at: 2026-08-10
---

# 09 - LiteLLM LLM Gateway

## Status

Accepted (2026-07-20).

## Purpose

This ADR selects **[LiteLLM](https://docs.litellm.ai/)** as the approved **LLM gateway** for Astloom. All platform-initiated model calls (chat/completions, structured judge outputs, documentation generation, and provider-backed embeddings when not using a local stub) must go through LiteLLM.

Astloom remains a control plane: it does not replace coding IDEs or agent frameworks. LiteLLM is the **infrastructure adapter** that unifies provider APIs so domain and application layers stay provider-agnostic.

## Professional Audience

Platform architects, backend service engineers (rule-engine, code-graph, memory, adapter), security reviewers, and operators configuring model credentials and routing profiles.

## Context

- Designs reference tiered local/cloud routing (`docs/07-code-knowledge-graph/05-token-optimization-and-model-routing.md`) without naming a gateway.
- Gap register **GAP-003** required a concrete LLM provider / local model strategy.
- Calling vendor SDKs (OpenAI, Anthropic, etc.) directly from multiple services would violate the product-per-role rule and complicate secrets, retries, and observability.

## Decision

1. **LiteLLM is the sole approved LLM gateway** for Astloom services and workers.
2. Application code depends on a **port** (for example `LlmCompletionPort` / `LlmEmbeddingPort`), not on LiteLLM types.
3. The infrastructure adapter implements that port with the **LiteLLM Python SDK** and/or a **self-hosted LiteLLM proxy** when operators need a shared network gateway.
4. **ModelRoutingProfile** (tenant / project / task / risk) maps to LiteLLM **model aliases** (for example `gpt-4o`, `ollama/qwen2.5-coder`, `azure/<deployment>`). Profiles own *which* model; LiteLLM owns *how* to call it.
5. Domain and application layers **must not** import `openai`, `anthropic`, or other vendor SDKs for model calls. Tests use fakes behind the port; live tests may call LiteLLM against configured backends.
6. Secrets (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, Azure / Ollama endpoints, etc.) are configured for LiteLLM via environment or proxy config — never hard-coded in services.
7. Structured LLM-as-a-judge and documentation generation must request **JSON / schema-constrained** outputs through the port; LiteLLM is the transport, not the policy owner.

## Non-Goals

- Replacing IDE / agent-runtime model calls that run **outside** Astloom (Cursor, LangGraph workers may use their own providers). Astloom-owned services still use LiteLLM when *Astloom* invokes a model.
- Replacing PostgreSQL+pgvector as the durable embedding **store**. LiteLLM may produce embedding vectors; storage remains pgvector (see stack docs). Local deterministic stubs (`LocalEmbeddingStub`) remain allowed for offline tests and Phase 7 slices until a routing profile selects a real embedding model.
- Mandating a specific cloud vendor. LiteLLM exists so vendors remain swappable.

## Architecture Sketch

```text
Use case (docs, judge, generation)
        │
        ▼
 LlmCompletionPort / LlmEmbeddingPort   (application port)
        │
        ▼
 LiteLLMAdapter  ──►  LiteLLM SDK and/or LiteLLM Proxy
        │
        ├── OpenAI / Azure OpenAI
        ├── Anthropic
        ├── Ollama / vLLM / local OpenAI-compatible
        └── other LiteLLM-supported providers
```

## Configuration Expectations

| Concern | Rule |
| --- | --- |
| Model id | LiteLLM model string or alias from `ModelRoutingProfile` |
| Timeout / retry | Configured on the adapter or proxy; bounded per task class |
| Cost / tokens | Recorded in observability (model, prompt/completion tokens, latency, tenant/project) |
| Failure | Surface typed errors to application; policy decides fallback or escalation |
| Local default | Prefer Ollama / OpenAI-compatible local endpoints for low-risk docs when profile says so |

Example environment shape (illustrative — not a secret store):

```bash
ASTLOOM_LITELLM_ENABLED=true
ASTLOOM_LITELLM_HOST=127.0.0.1
ASTLOOM_LITELLM_PORT=32400
## Leave empty for auto Base URL http://127.0.0.1:32400 — or override:
## ASTLOOM_LITELLM_API_BASE=http://127.0.0.1:32400
ASTLOOM_LITELLM_API_KEY=<proxy-or-provider-key>
ASTLOOM_LITELLM_DEFAULT_MODEL=ollama/qwen2.5-coder
ASTLOOM_LITELLM_TIMEOUT_SECONDS=180
ASTLOOM_LITELLM_NUM_RETRIES=3
ASTLOOM_LITELLM_RPM=30
```

Host ports must follow `backend/configs/port-profiles/` (`ASTLOOM_LITELLM_PORT=32400`; do not use LiteLLM upstream default `4000`).

Shared package: `backend/packages/llm_gateway`. Discovery: `GET /api/v1/llm/providers` or `python -m llm_gateway providers`.

## Consequences

### Positive

- One integration surface for many providers.
- Easier ModelRoutingProfile implementation and tenant overrides.
- Central place for retries, fallbacks, and spend controls.

### Negative / follow-ups

- LiteLLM becomes a critical dependency; pin versions in `.venv` / lockfiles.
- Operators must understand LiteLLM model strings and proxy ops.
- Concrete default profiles (exact model names per task/risk) still need product/ops tables; this ADR only locks the **gateway**.

## Acceptance Criteria

- Normative stack docs list LiteLLM as the LLM gateway product-per-role owner.
- GAP-003 is closed with resolution pointing here.
- New LLM call sites in Astloom services use the port + LiteLLM adapter (no new direct vendor SDK usage).
- Unit tests do not require network; live gates may exercise LiteLLM when credentials/endpoints are present.
- Code-graph documentation generation and rule-engine LLM judge designs reference this ADR when they leave heuristic/stub mode.

## Related

- Product-per-role: `07-service-product-standard.md`
- Backend stack: `03-backend-api-and-service-stack.md`
- Tiered routing strategy: `docs/07-code-knowledge-graph/05-token-optimization-and-model-routing.md`
- Gap register: `GAP-003` in `docs/10-gap-analysis/01-gap-register.md`
- RPM-session parallel sync (designed, not shipped): `docs/07-code-knowledge-graph/37-rpm-session-parallel-sync-feature-specification.md` through `40-…-acceptance.md` — evolves client-side RPM from start-only timestamps to tracked sessions with CLI/HTTP observability.
