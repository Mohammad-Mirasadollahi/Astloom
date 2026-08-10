# Production retrieval fuzzer suite (50 cases)

Adversarial + live noise suite for tokenize / Lucene / BM25 / RRF / GDS clamp /
communities / hybrid / explore / Postgres FTS.

Normative runbook:
[`docs/07-code-knowledge-graph/33-production-retrieval-live-test-gates.md`](../../../docs/07-code-knowledge-graph/33-production-retrieval-live-test-gates.md)

## Prerequisites

```bash
backend/deployments/compose/wait-healthy.sh --timeout 90 astloom-neo4j-1 astloom-postgres-1
```

## Run

```bash
export ASTLOOM_NEO4J_PASSWORD=astloom-local-dev-secret
export ASTLOOM_POSTGRES_PASSWORD=astloom-local-dev-secret

PYTHONPATH=backend/services/code-graph-service/src \
  .venv/bin/python -m pytest \
  tests/backend/services/code-graph-service/test_production_retrieval_fuzzer.py -v
```

Artifacts: `tests/artifacts/code-graph-live/fuzzer-*`.

## Mix (50)

| Kind | Count | Coverage |
| --- | ---: | --- |
| Unit simple | ~20 | tokenize, Lucene escape, BM25 empty/miss, RRF empty, GDS clamp happy path |
| Unit challenge | ~19 | unicode/emoji/oversized query, Lucene specials, huge body, weird graphs |
| Live simple | ~4 | hybrid+explore baseline, empty query reject, architecture+path |
| Live challenge | ~7 | Lucene/path traversal queries, Postgres FTS weird, GDS off, random BM25 soup |
