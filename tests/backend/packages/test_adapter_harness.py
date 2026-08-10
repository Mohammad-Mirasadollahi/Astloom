"""GAP-T06: adapter harness capability validate, secret-ref, mock adapter contracts."""

from __future__ import annotations

import pytest

from adapter_harness import (
    CapabilityError,
    ContractCase,
    MockAdapter,
    SecretRefError,
    declare_capabilities,
    run_contract_tests,
    secret_ref,
    validate_capabilities,
)


def test_declare_and_validate_capabilities():
    decl = declare_capabilities("mock.adapter", "1.0.0", ["health.check", "echo"])
    assert validate_capabilities(decl, required={"health.check"}) == []
    assert validate_capabilities(decl, required={"health.check", "missing"}) == ["missing"]


def test_declare_capabilities_fail_closed():
    with pytest.raises(CapabilityError):
        declare_capabilities("", "1.0.0", ["echo"])
    with pytest.raises(CapabilityError):
        declare_capabilities("a", "1", [])


def test_secret_ref_name_only_never_value():
    ref = secret_ref("mock.api_token")
    assert ref.to_dict() == {"name": "mock.api_token"}
    with pytest.raises(SecretRefError):
        secret_ref("bad=value")
    with pytest.raises(SecretRefError):
        secret_ref("")


def test_mock_adapter_contract_runner_passes():
    adapter = MockAdapter()
    results = run_contract_tests(
        adapter,
        [
            ContractCase(
                name="health",
                required_capabilities=frozenset({"health.check"}),
                invoke_capability="health.check",
            ),
            ContractCase(
                name="echo",
                required_capabilities=frozenset({"echo"}),
                invoke_capability="echo",
                invoke_payload={"ping": True},
            ),
        ],
    )
    assert all(r.ok for r in results), results
    assert adapter.invocations[1][0] == "echo"


def test_mock_adapter_missing_capability_fails_closed():
    adapter = MockAdapter(capabilities=["echo"])
    results = run_contract_tests(
        adapter,
        [
            ContractCase(
                name="need-health",
                required_capabilities=frozenset({"health.check"}),
                expect_ok=False,
            )
        ],
    )
    assert results[0].ok is True  # expect_ok=False and missing → ok
    assert "missing" in results[0].detail
