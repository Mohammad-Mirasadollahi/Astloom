# E2E Graph Probe Sample

This tiny Python package exists only to validate Astloom code-graph ingest.

## Expected graph shape

- Symbols: `hash_password`, `verify_password`, `login`, `require_login`
- Calls: `verify_password` → `hash_password`, `login` → `verify_password`, `require_login` → `login`
- Docs: module/function docstrings (and optional LiteLLM `ai_documentation` on changed symbols)

## How to re-run

See `samples/e2e-graph-probe/README.md`.
