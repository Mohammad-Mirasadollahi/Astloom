# Neo4j Python ingest acceptance gate

Runs live/parity/hybrid pytest targets for `code-graph-service` against Compose Neo4j + Postgres on non-default ports.

```bash
# Optional: wait with hard timeout first
backend/deployments/compose/wait-healthy.sh --timeout 90 astloom-neo4j-1 astloom-postgres-1

# Soft gate (skips reachability if down; pytest skips live tests)
.venv/bin/python tests/backend/gates/neo4j-python-ingest/run_gate.py

# Strict gate (fail if ports down)
.venv/bin/python tests/backend/gates/neo4j-python-ingest/run_gate.py --require-live --json

# Production retrieval live suite (simple + challenge; BM25/FTS/explore/GDS)
# See tests/backend/services/code-graph-service/README_production_retrieval_live.md
ASTLOOM_NEO4J_PASSWORD=… ASTLOOM_POSTGRES_PASSWORD=… \
  PYTHONPATH=backend/services/code-graph-service/src \
  .venv/bin/python -m pytest \
  tests/backend/services/code-graph-service/test_production_retrieval_live.py -v
```

Environment defaults match the Astloom port profile (`32287` Bolt, `32232` Postgres).
