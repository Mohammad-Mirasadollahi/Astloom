# LLM Gateway (LiteLLM)

Path: `backend/packages/llm_gateway`

## Purpose

Shared LiteLLM adapter for Astloom services. Implements the stack ADR
`docs/13-technology-stack-and-platform-decisions/09-litellm-llm-gateway.md`.

## Environment

**Full operator reference (every variable, change impact, worked examples):**  
[`docs/13-technology-stack-and-platform-decisions/12-litellm-environment-configuration.md`](../../../docs/13-technology-stack-and-platform-decisions/12-litellm-environment-configuration.md)

**Copy template (repo root):**  
`.env.example` → `.env`

| Variable | Default | Meaning |
| --- | --- | --- |
| `ASTLOOM_LITELLM_ENABLED` | `true` | Master switch |
| `ASTLOOM_LITELLM_HOST` | `127.0.0.1` | Host for **auto** Base URL |
| `ASTLOOM_LITELLM_PORT` | profile `32400` | Port for **auto** Base URL |
| `ASTLOOM_LITELLM_API_BASE` | _(empty)_ | Optional Base URL **override** (if set, replaces auto) |
| `LITELLM_API_BASE` | _(empty)_ | Alias override when `ASTLOOM_LITELLM_API_BASE` unset |
| `ASTLOOM_LITELLM_API_KEY` | _(empty)_ | Gateway/proxy key (falls back to `LITELLM_API_KEY` / `OPENROUTER_API_KEY` / `OPENAI_API_KEY`) |
| `ASTLOOM_LITELLM_DEFAULT_MODEL` | _(empty)_ | Default LiteLLM model alias |
| `ASTLOOM_LITELLM_TIMEOUT_SECONDS` | `180` | Request timeout |
| `ASTLOOM_LITELLM_NUM_RETRIES` | `3` | LiteLLM `num_retries` |
| `ASTLOOM_LITELLM_RPM` | `30` | Max requests per rolling minute (client-side limiter) |
| `ASTLOOM_LITELLM_DROP_PARAMS` | `true` | `litellm.drop_params` |
| `ASTLOOM_LITELLM_DEBUG` | `false` | Calls `litellm._turn_on_debug()` once; tip spam always suppressed |
| `ASTLOOM_LITELLM_REASONING_ENABLED` | `false` | Send OpenRouter-style `reasoning.enabled` via `extra_body` |
| `ASTLOOM_LITELLM_REASONING_EFFORT` | _(empty)_ | Optional `reasoning.effort` when enabled |
| `ASTLOOM_LITELLM_DOCS_ENABLED` | `true` | Use LiteLLM for symbol docs (heuristic fallback) |
| `ASTLOOM_LITELLM_EMBEDDINGS_ENABLED` | `false` | Use LiteLLM embeddings (stub fallback; vectors reduced to 16-d) |
| `ASTLOOM_LITELLM_MODEL_DOCS` / `_EMBED` / `_JUDGE` / `_CODEGEN` | _(empty)_ | Per-task model overrides |
| `ASTLOOM_LITELLM_ROUTING_ENV` | `local` | Select `default.json` (`local`) or `cloud.json` profile |
| `ASTLOOM_LITELLM_ROUTING_PROFILE` | _(empty)_ | Optional path to a custom ModelRoutingProfile JSON |
| `ASTLOOM_LITELLM_FALLBACK_MODELS` | _(empty)_ | Comma-separated fallback aliases |
| `ASTLOOM_LITELLM_RISK_LEVEL` | `low` | Routing risk: `low` / `medium` / `high` |
| `ASTLOOM_LITELLM_PROFILE_ID` | _(profile file)_ | Route profile label override |
| `ASTLOOM_CONTEXT_COMPRESS` | `1` | Compress long message contents before LiteLLM (`0`/`false`/`off` to disable) |
| `ASTLOOM_CONTEXT_COMPRESS_MIN_CHARS` | `2000` | Skip compression below this length |

Auto Base URL: `http://{HOST}:{PORT}` when no override is set.

## CLI

```bash
astloom llm test
astloom llm test --prompt "Hi" --model openai/gpt-oss-120b
PYTHONPATH=backend/packages .venv/bin/python -m llm_gateway providers
PYTHONPATH=backend/packages .venv/bin/python -m llm_gateway config
PYTHONPATH=backend/packages .venv/bin/python -m llm_gateway complete --prompt "ping"
PYTHONPATH=backend/packages .venv/bin/python -m llm_gateway complete --prompt "ping" --reasoning
```

## Status

Implemented: `RpmSessionGate` tracks session start/end and in-flight count;
`LiteLlmGateway` / `FakeLlmGateway` acquire/release around `complete`/`embed`.
Observability: `gateway.rpm_sessions_snapshot()`, HTTP `GET /api/v1/llm/sessions`,
CLI `astloom llm sessions`. Design pack:
[`docs/07-code-knowledge-graph/37-rpm-session-parallel-sync-feature-specification.md`](../../../docs/07-code-knowledge-graph/37-rpm-session-parallel-sync-feature-specification.md)
through `40`.
