# edit_session

## Purpose

Session-scoped **IDE-semantic** tooling (local Language Server Protocol) for
find-references, go-to-definition, and rename. Complements durable AST ingest;
never writes `CODE_REL`.

## Boundaries

- **In:** workspace root + path + cursor position; optional `ASTLOOM_LSP_CMD_*`.
- **Out:** `reference_kind=ide_semantic` payloads; disk WorkspaceEdit; then
  `reconcile_after_edit` → AST re-ingest.
- **Not here:** Neo4j/Postgres graph writers, JetBrains plugin, cloud LS.

## Start here

| File | Role |
|------|------|
| `protocol.py` | `EditSessionPort` |
| `lsp_session.py` | Real stdio LSP session + factory |
| `fake.py` | Deterministic test double |
| `../application/edit_session.py` | HTTP/MCP use cases |

ADR / feature: `docs/07-code-knowledge-graph/48-…`, `49-…`.
