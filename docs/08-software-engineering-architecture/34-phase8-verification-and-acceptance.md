---
doc_id: as.doc.sea.phase8-verification-and-acceptance
title: Phase 8 - Verification and Acceptance
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Phase 8 is a documentation-and-governance phase. Its executable gate does not invent
  a new product microservice. It proves that the software engineering playbook is present,
  service ownership and contracts exist, and development ports are configurable, non-default,
  and validated.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/34-phase8-verification-and-acceptance.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- tests/backend/gates/port-profile-verification/run_gate.py::main
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Phase 8 - Verification and Acceptance

## Purpose

Phase 8 is a documentation-and-governance phase. Its executable gate does not invent a new product microservice. It proves that the software engineering playbook is present, service ownership and contracts exist, and development ports are configurable, non-default, and validated.

## Gate Artifacts

| Artifact | Path |
| --- | --- |
| Playbook docs | `docs/08-software-engineering-architecture/` |
| Port profile | `backend/configs/port-profiles/astloom-dev.json` |
| Port loader | `backend/packages/port_profile/` |
| Verification package | `tests/support/port_profile_gate/` |
| Gate tests | `tests/backend/gates/port-profile-verification/` |

## Named Commands

```bash
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/port-profile-verification -q
.venv/bin/python tests/backend/gates/port-profile-verification/run_gate.py
.venv/bin/python tests/backend/gates/port-profile-verification/run_gate.py --run-suites
```

## Exit Checks Covered by the Gate

- Required Phase 8 engineering documents exist and contain key topic markers.
- Every owned runtime service (core-data through adapter, plus code-graph) has source, tests, README, and an owned API contract.
- Development port profile exists, rejects common default ports, supports `ASTLOOM_*_PORT` overrides, and maps each owned service to a port key.
- Optional `--run-suites` executes canonical pytest suites for owned services.

## Acceptance

Phase 8 passes when `check_phase_gate(run_suites=False)` returns `pass` and `run_all_checks()` returns only `passed` results. A documented waiver reference may mark the gate `waived` when an explicit owner accepts temporary failures.
