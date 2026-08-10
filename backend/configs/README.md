# Configs

Path: `backend/configs`

## Purpose

Versioned backend configuration templates and machine-readable catalogs used by services and phase gates.

## Contents

| Directory | Role |
|-----------|------|
| `port-profiles/` | Development port profile (`astloom-dev.json`) |
| `governance/` | Risk/decision catalog, impact KPIs, gap register |
| `logical-examples/` | Phase 11 examples catalog |
| `domain-packs/` | Domain pack defaults |
| `feature-profiles/` | Feature profile defaults |
| `rule-packs/` | Rule pack defaults |
| `common-context-profiles/` | Common-context scoring defaults |
| `technology-profiles/` | Technology baseline profiles |
| `code-metadata-profiles/` | Code-metadata validation profiles |
| `environments/` | Environment profiles (`local` … `prod`) |
| `model-routing/` | Default local/cloud `ModelRoutingProfile` tables (LiteLLM aliases) |
| `embeddings/` | Embedding refresh policy (GAP-T03 lifecycle / model-change / TurboVec sync) |

## Rules

- Keep ownership clear and local to this boundary.
- Do not hard-code ports, credentials, tenant IDs, project IDs, model names, provider endpoints, or feature behavior in application code; bind through these configs.
- Prefer dependency inversion: domain and application logic should not depend on infrastructure implementation details.
- Use shared packages only for stable contracts or cross-cutting primitives.
- Add or update tests and documentation when this boundary receives implementation code.

## Status

Active configuration home for Phase 8–11 gates and platform defaults. Loaders live under `backend/packages/` (`port_profile`, `governance_catalog`, `logical_examples`, `shared-kernel`, `code-metadata`, `common-context`).
