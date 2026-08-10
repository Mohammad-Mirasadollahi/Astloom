# Adapter Service tests

Executable tests for the interoperability / adapter vertical slice (`adapter-service`).

```bash
PYTHONPATH=backend/services/adapter-service/src .venv/bin/python -m pytest tests/backend/services/adapter-service -q
```

Focused ExternalTicket coverage for the modular `adapter_service.core` package lives in `test_external_tickets.py` (create validation, sync/cancel, fallback status policy, push conflict + HTTP route, dispatch result validation, helpers, local-adapter fallback). Broader interop regression remains in `test_adapter_service.py`.

The unit suite may use `InMemoryStore`. Durable behavior belongs to the canonical main-infrastructure test:

```bash
tests/live/adapter-service/run-main-infrastructure.sh
```
