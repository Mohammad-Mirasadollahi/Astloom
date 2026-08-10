# context_compression

Path: `backend/packages/context_compression/`

## Purpose

Native Astloom context compression (Headroom-inspired, clean-room): shrink bulky
JSON/text before LiteLLM / MCP agents, with tenant-scoped TTL retrieve.

## Boundaries

- **Owns:** lossless JSON minify + bounded lossy truncation; in-process CCR-like store.
- **Does not own:** code-graph packing, IDE `ai-toolstack` Headroom, LLM provider calls.
- **Law:** `docs/07-code-knowledge-graph/54-headroom-native-context-compression.md`

## Start here

| File | Role |
| --- | --- |
| `compress.py` | Detect type; minify JSON; truncate long strings/lists |
| `store.py` | Scope-keyed TTL store; handle mint/retrieve |
| `metrics.py` | Process-local savings counters (`astloom context stats`) |
| `__init__.py` | Public API |

## CLI

```bash
astloom context measure --file /path/to/blob.json
astloom context measure --payload '{"rows":[1,2,3]}' --min-chars 1 --json
astloom context stats
```

`measure` reports one-shot savings and appends to `.astloom/cache/context-compression-metrics.json`.
`stats` prints those CLI totals. Live MCP gateway counters: `astloom_context_stats`.

## Related

- MCP: `mcp_gateway_service.backends.context`
- LiteLLM: `llm_gateway.gateway.LiteLlmGateway.complete`
