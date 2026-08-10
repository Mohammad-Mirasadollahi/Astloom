# Governance catalog verification

Canonical gate for platform governance catalogs (risks, impact KPIs).

```bash
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/governance-catalog-verification -q
.venv/bin/python tests/backend/gates/governance-catalog-verification/run_gate.py
```

See `docs/09-platform-governance-operations/11-phase9-verification-and-acceptance.md`.
