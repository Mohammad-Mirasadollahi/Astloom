# Code Graph Service tests

Canonical tests for `code-graph-service`.

`pyproject.toml` sets `pythonpath` for `backend/services/code-graph-service/src`
(see `docs/07-code-knowledge-graph/33-production-retrieval-live-test-gates.md`).

```bash
.venv/bin/python -m pytest tests/backend/services/code-graph-service -q

# Live gates (Compose Neo4j + Postgres on non-default ports):
export ASTLOOM_NEO4J_PASSWORD=astloom-local-dev-secret
export ASTLOOM_POSTGRES_PASSWORD=astloom-local-dev-secret
.venv/bin/python -m pytest \
  tests/backend/services/code-graph-service/test_production_retrieval_live.py \
  tests/backend/services/code-graph-service/test_production_retrieval_fuzzer.py \
  tests/backend/services/code-graph-service/test_production_retrieval_challenge_live.py -q

# Slow-sync seam (store vs Provider): stub rate gate always; Provider compare opt-in
.venv/bin/python -m pytest \
  tests/backend/services/code-graph-service/test_sync_provider_vs_store_latency_live.py -m live -v
# ASTLOOM_DIAG_PROVIDER_LIVE=1 … same file (burns OpenRouter RPM)
```
