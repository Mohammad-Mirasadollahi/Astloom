# Model routing profiles

Path: `backend/configs/model-routing`

## Purpose

Versioned `ModelRoutingProfile` defaults for LiteLLM task/risk → model alias
resolution (GAP-003). Normative design:
`docs/13-technology-stack-and-platform-decisions/10-model-routing-profiles-with-litellm.md`.

## Files

| File | Role |
|------|------|
| `model-routing-profile.schema.json` | JSON Schema for profiles |
| `default.json` | Local/lab defaults (`environment: local`, Ollama aliases) |
| `cloud.json` | Cloud/API defaults (`environment: cloud`) |

## Selection

- `ASTLOOM_LITELLM_ROUTING_ENV=local|cloud` (default `local`) selects which
  built-in file feeds `llm_gateway.resolve_route` when per-task env vars are empty.
- `ASTLOOM_LITELLM_ROUTING_PROFILE` may point at an absolute/relative JSON path.
- Per-task env (`ASTLOOM_LITELLM_MODEL_DOCS`, …) and
  `ASTLOOM_LITELLM_FALLBACK_MODELS` still override the file.
