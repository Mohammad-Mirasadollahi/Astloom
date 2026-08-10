# Migrations

Path: `backend/services/memory-service/migrations`

## Purpose

Service-owned persistence migrations. Parent service: `services/memory-service`.

## Modular Boundary

This directory is part of the Astloom backend modular architecture. It must expose behavior through documented contracts, public interfaces, configuration, or events. It must not import private internals from sibling modules.

## Allowed Contents

- README and design notes for this boundary.
- Source, configuration, fixtures, tests, or generated artifacts that belong to this boundary.
- Subdirectories that follow the backend structure standard.

## Rules

- Keep ownership clear and local to this boundary.
- Do not hard-code ports, credentials, tenant IDs, project IDs, model names, provider endpoints, or feature behavior.
- Prefer dependency inversion: domain and application logic should not depend on infrastructure implementation details.
- Use shared packages only for stable contracts or cross-cutting primitives.
- Add or update tests and documentation when this boundary receives implementation code.

## Status

Active. `0001_memory.sql` owns the `memory` schema, memory items, question memory, work batches, durable idempotency records, and outbox events. `0003_memory_embeddings.sql` is the pgvector SoR; `0004_embedding_id_map.sql` is the optional TurboVec entity id map (apply with operator migrations). `0005_memory_retention.sql` adds `pinned` and `expires_at` for human remember/forget.
