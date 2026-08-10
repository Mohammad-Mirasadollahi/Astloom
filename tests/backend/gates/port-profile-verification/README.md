# Port-profile verification

Canonical gate for port profiles, shared packages, and service ownership boundaries.

```bash
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/port-profile-verification -q
.venv/bin/python tests/backend/gates/port-profile-verification/run_gate.py
```
