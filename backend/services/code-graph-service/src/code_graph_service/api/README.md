# api — HTTP transport for code-graph-service

**Owns:** FastAPI `build_app`, request schemas, route handlers.  
**Does not:** durable graph writes, AST/LSP domain logic (those live under `application/` / `domain/`).

## Start here

| File | Role |
|------|------|
| `__init__.py` | `build_app` / `app` factory; attaches `api.state.container` |
| `schemas.py` | Pydantic request bodies |
| `common.py` | `scope_from`, loopback check, `CodeGraphError` handler |
| `ingest.py` / `query.py` / `intelligence.py` | Graph ingest + read/intelligence routes |
| `edit_session.py` | ADR 48 reconcile + Feature 49 LSP session routes |
| `generation.py` / `llm.py` / `health.py` | Generation pack, LiteLLM proxy, `/health` |
