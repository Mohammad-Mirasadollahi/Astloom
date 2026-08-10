# vector_index

## Purpose

Shared `VectorIndexPort` for optional in-process ANN acceleration (turbovec `IdMapIndex`). PostgreSQL + pgvector remains the durable embedding SoR.

## Boundaries

- May: expose port, in-memory fake, config helpers, entity_ref↔uint64 map, TurboVec adapter (lazy import).
- Must not: own ACL/lifecycle; replace pgvector; import turbovec from domain layers; use `TurboQuantIndex`.

## Start here

1. `port.py` — `VectorIndexPort` (incl. `rebuild_from_rows`)
2. `turbovec_adapter.py` — optional vendor wrapper
3. `in_memory.py` — unit-test fake
4. `id_map.py` — durable id mapping + SQL snippet (`PostgresEntityIdMap`)
5. `config.py` — `ASTLOOM_RAG_ANN_*` / `ASTLOOM_TURBOVEC_*`
6. `factory.py` — `try_build_accelerator` (snapshot load + metrics wrap)
7. `metrics.py` — process-local counters + `InstrumentedVectorIndex`
8. `promotion_gate.py` — recall@k / latency / RSS proxy vs dense baseline
