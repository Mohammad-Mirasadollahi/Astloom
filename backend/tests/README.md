# Backend Test Placeholder

Executable backend tests must live under the repository-level `tests/backend/` directory.

This path remains as a backend architecture placeholder only. Do not add runnable `test_*.py`, `*_test.py`, or framework-specific test files here. Put new backend tests in:

```text
tests/backend/<service-or-app-name>/
```

For Phase 1 Core Data Service, use:

```bash
PYTHONPATH=backend/services/core-data-service/src .venv/bin/python -m pytest tests/backend/services/core-data-service
```
