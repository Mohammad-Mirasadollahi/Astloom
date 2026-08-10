# Technical logic verification

Path: `tests/backend/gates/technical-logic-verification`

## Purpose

Executable gate for technical logic across owned vertical-slice services. This is not a product microservice. It checks canonical paths, contracts, state machines, idempotency, redaction, and an in-process end-to-end runtime scenario for:

- `core-data-service`
- `memory-service`
- `docs-sync-service`
- `rule-engine-service`
- `adapter-service`

## Layout

- Harness package: `tests/support/technical_logic/`
- Tests: `test_technical_logic.py`
- Gate CLI: `run_gate.py`

## Run

```bash
PYTHONPATH=tests/support .venv/bin/python -m pytest tests/backend/gates/technical-logic-verification
```

Full gate including owned service suites:

```bash
.venv/bin/python tests/backend/gates/technical-logic-verification/run_gate.py --run-suites
```

Machine-readable report:

```bash
.venv/bin/python tests/backend/gates/technical-logic-verification/run_gate.py --json
```
