# Embeddings configs

Path: `backend/configs/embeddings`

## Purpose

Machine-readable embedding lifecycle and refresh policy for code-graph and memory SoR paths (GAP-T03).

## Contents

| File | Role |
|------|------|
| `refresh-policy.json` | Active refresh policy (model, dims, skip rules, states, tenant scope, TurboVec replica sync) |
| `refresh-policy.schema.json` | JSON Schema (draft 2020-12) for the policy document |

## Rules

- Durable embeddings remain PostgreSQL + pgvector (`vector(1024)` for BGE-large).
- TurboVec is an optional rebuildable replica; sync only after successful SoR write.
- Cross-project refresh is forbidden; jobs always bind `tenant_id` / `workspace_id` / `project_id`.
- Operator enablement: root `.env` / `.env.example` (`ASTLOOM_RAG_ANN_ACCELERATOR`, default `off`). Guide: `docs/13-technology-stack-and-platform-decisions/11-turbovec-for-rag.md`.
