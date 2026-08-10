# Change Society Service Tests

Executable unit, contract, API, provider-adapter, SDK, and regression tests for the hackathon Agent Society vertical slice.

## Run

```bash
PYTHONPATH=archives/hackathon/backend/change-society-service/src:archives/hackathon/sdk/python .venv/bin/python -m pytest tests/backend/legacy/change-society-service -q
```

Optional live Qwen gate (skipped without `QWEN_API_KEY`):

```bash
QWEN_API_KEY=... PYTHONPATH=archives/hackathon/backend/change-society-service/src:archives/hackathon/sdk/python .venv/bin/python -m pytest tests/backend/legacy/change-society-service/test_qwen_live.py -q
```

Frontend state/API helpers:

```bash
node --experimental-strip-types --test tests/frontend/change-society/*.test.mjs
```

## Coverage Map

| Module / concern | Test file(s) |
|---|---|
| Domain policies (`stable_digest`, conflict, approval) | `test_domain_policies.py` |
| Domain control plane (agent/ticket invariants) | `test_domain_control_plane.py` |
| Evaluation scoring and baseline fairness | `test_evaluation.py`, `test_change_society.py` |
| Evidence catalog filtering and memory scope | `test_evidence_catalog.py` |
| In-memory run repository | `test_repositories.py` |
| Control plane routing, tickets, heartbeat | `test_control_plane_application.py` |
| Qwen/fake model adapters | `test_qwen_adapter.py`, `test_infrastructure_clients.py`, `test_qwen_live.py` |
| Webhook/model agent adapters | `test_agent_adapters.py` |
| Bootstrap configuration validation | `test_bootstrap_config.py` |
| FastAPI transport (pagination, readiness, errors) | `test_interfaces_api.py`, `test_change_society.py` |
| Society workflow, idempotency, scenarios | `test_change_society.py`, `test_service_decisions.py` |
| Universal Agent JSON contracts | `test_contracts.py` |
| Python SDK | `test_sdk.py`, `test_sdk_errors.py` |
| Runtime SDK (LangChain/LangGraph/webhook) | `test_agent_runtime_sdk.py` |
| Frontend demo state + API errors | `tests/frontend/change-society/*.test.mjs` |

## Remaining Non-Unit Gates

- End-to-end evidence scripts: `tests/e2e/change-society/run-real-test.sh`, `tests/live/change-society/run-live-test.sh`
- PostgreSQL repository integration (requires database)
- Alibaba public deployment smoke (requires entrant credentials)
