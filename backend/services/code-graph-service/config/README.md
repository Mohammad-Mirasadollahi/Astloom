# Config

Path: `backend/services/code-graph-service/config`

## Purpose

Placeholder directory for future non-env service assets. **Operator environment
(LiteLLM, Neo4j, embeddings, optional Stage-2 ANN, scope) is not here** — use the
repository-root `.env` (template: `.env.example`).

## Operator reference (normative)

`docs/13-technology-stack-and-platform-decisions/12-litellm-environment-configuration.md`

Related ADRs:

- `docs/13-technology-stack-and-platform-decisions/09-litellm-llm-gateway.md`
- `docs/13-technology-stack-and-platform-decisions/10-model-routing-profiles-with-litellm.md`
- `docs/13-technology-stack-and-platform-decisions/08-turbovec-ann-acceleration-integration.md`
- `docs/13-technology-stack-and-platform-decisions/11-turbovec-for-rag.md`

## How to use

1. Copy repo-root `.env.example` to `.env` (or let `install.sh` / `astloom init` create it).
2. Edit models, keys, store settings, and (optionally) `ASTLOOM_RAG_ANN_ACCELERATOR` in that root `.env`.
3. CLI loads root `.env` automatically:

```bash
set -a && source .env && set +a
```

4. Verify: `PYTHONPATH=backend/packages python -m llm_gateway config` or `GET /api/v1/llm/config`.
5. ANN default is `off` (pgvector Stage-1 only). To enable Turbovec Stage-2, install `.[turbovec]`, set `ASTLOOM_RAG_ANN_ACCELERATOR=turbovec`, then run `python -m vector_index.promotion_gate`.

## Rules

- Do not add a service-local `.env` template here; keep a single operator env at the repo root.
- When adding a new env variable, update root `.env.example` and `12-litellm-environment-configuration.md` (plus continuation for embedding/ANN knobs).
