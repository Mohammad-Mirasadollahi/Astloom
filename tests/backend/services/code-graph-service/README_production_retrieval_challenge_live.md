# Production retrieval — 50 live challenge tests

Adversarial live gate against Compose Neo4j + Postgres.

Normative runbook:
[`docs/07-code-knowledge-graph/33-production-retrieval-live-test-gates.md`](../../../docs/07-code-knowledge-graph/33-production-retrieval-live-test-gates.md)

## Prerequisites

```bash
backend/deployments/compose/wait-healthy.sh --timeout 90 astloom-neo4j-1 astloom-postgres-1
export ASTLOOM_NEO4J_PASSWORD=astloom-local-dev-secret   # must match Compose
export ASTLOOM_POSTGRES_PASSWORD=astloom-local-dev-secret
```

If password does **not** match Compose, older runs showed ~48 setup ERRORs + fails
(looks like “50 failed”). Suites now **skip** with a clear AuthError message instead.

`pyproject.toml` sets `pythonpath` for `code_graph_service` so Test Explorer works
without exporting `PYTHONPATH`.

## Run

```bash
export ASTLOOM_NEO4J_PASSWORD=astloom-local-dev-secret
export ASTLOOM_POSTGRES_PASSWORD=astloom-local-dev-secret

PYTHONPATH=backend/services/code-graph-service/src \
  .venv/bin/python -m pytest \
  tests/backend/services/code-graph-service/test_production_retrieval_challenge_live.py -v
```

Artifacts: `tests/artifacts/code-graph-live/challenge-*`.

## Mix (50)

| Block | Count |
| --- | ---: |
| Hybrid adversarial queries | 20 |
| Explore adversarial queries | 10 |
| top_k extremes | 5 |
| path/neighbors depth | 4 |
| Hard singles (RRF, GDS-off, Postgres FTS, freshness, …) | 11 |
