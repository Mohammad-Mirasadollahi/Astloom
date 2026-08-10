# Backend Tests

Backend tests are nested by category, then by owning service or feature.

```text
tests/backend/
  services/<service>/     mirrors backend/services/<service>/
  gates/<feature>-verification/
  packages/               shared package loaders
  tools/                  astloom-cli, outbox-relay, usage-profile
  platform/               cross-cutting smokes (service entrypoints)
  legacy/                 archived Change Society suites
```

## Suites

| Path | Role |
|------|------|
| `services/core-data-service/` | Core data model service |
| `services/memory-service/` | Memory and context service |
| `services/docs-sync-service/` | Docs-as-code sync service |
| `services/rule-engine-service/` | Rule engine service |
| `services/adapter-service/` | Interoperability / adapter service |
| `services/code-graph-service/` | Code-knowledge graph service |
| `services/audit-service/` | Platform audit slice |
| `services/identity-access-service/` | Platform identity slice |
| `services/orchestration-service/` | Platform orchestration slice |
| `services/reporting-service/` | Platform reporting slice |
| `services/project-profile-service/` | Platform project-profile slice |
| `services/common-context-service/` | Platform common-context slice |
| `services/mcp-gateway-service/` | Cursor MCP gateway |
| `gates/technical-logic-verification/` | Technical-logic feature gate |
| `gates/port-profile-verification/` | Port-profile feature gate |
| `gates/governance-catalog-verification/` | Governance catalog feature gate |
| `gates/gap-register-verification/` | Gap-register feature gate |
| `gates/logical-examples-verification/` | Logical-examples feature gate |
| `packages/` | Shared package loaders |
| `tools/usage-profile/` | Usage Profile catalog loader |
| `tools/outbox-relay/` | Transactional outbox relay |
| `tools/astloom-cli/` | Astloom CLI |
| `platform/` | Cross-cutting platform smokes |
| `legacy/change-society-service/` | Archived hackathon suites |

Service-local `backend/**/tests/` directories are documentation-only placeholders. Canonical executable tests live here.

```bash
PYTHONPATH=backend/services/core-data-service/src .venv/bin/python -m pytest tests/backend/services/core-data-service -q
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/port-profile-verification -q
```

Full command list: [../README.md](../README.md).
