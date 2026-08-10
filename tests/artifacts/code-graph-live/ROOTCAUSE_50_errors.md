# Incident note — ~50 live ERROR cascade

**Canonical doc:** [`docs/07-code-knowledge-graph/33-production-retrieval-live-test-gates.md`](../../../docs/07-code-knowledge-graph/33-production-retrieval-live-test-gates.md)

## Symptom

Challenge/fuzzer live runs showed ~48 setup ERRORs + a few FAILUREs
(Test UI: “about 50 failed”).

## Root causes

1. Module-scoped Neo4j fixture `AuthError` / wrong `ASTLOOM_NEO4J_PASSWORD`
   re-reported per dependent test.
2. Missing pytest `pythonpath` → `ModuleNotFoundError: code_graph_service`.
3. Neo4j `AuthenticationRateLimit` after repeated bad logins amplified the flood.

## Fix

- `pythonpath` in `pyproject.toml` + directory `conftest.py`
- `live_helpers.skip_on_live_connect_error` on live fixtures
- Normative runbook: doc **33**

## Verified (2026-07-21)

- Correct Compose secrets → 50 challenge passed
- Wrong password → 50 skipped (not ERROR cascade)
