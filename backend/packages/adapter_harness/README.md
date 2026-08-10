# adapter_harness

Path: `backend/packages/adapter_harness`

## Purpose

Validate adapter capability maps, name-only secret references, and local/CI contract tests.

## Boundaries

- May: declare/validate capabilities, hold `SecretRef` names, run contract cases, ship mock fixture.
- Must not: store or log secret values, call production vendor APIs, bypass fail-closed required caps.

## Start here

1. `capability.py` — `declare_capabilities` / `validate_capabilities`
2. `secret_ref.py` — `SecretRef` (name only)
3. `contract_runner.py` — `run_contract_tests`
4. `fixtures/mock_adapter.py` — default fixture
