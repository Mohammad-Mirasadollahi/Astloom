"""Adapter harness — capability declare/validate, secret-ref, contract tests (GAP-T06)."""

from __future__ import annotations

from .capability import (
    CapabilityDeclaration,
    CapabilityError,
    declare_capabilities,
    validate_capabilities,
)
from .contract_runner import ContractCase, ContractResult, run_contract_tests
from .fixtures.mock_adapter import MockAdapter
from .secret_ref import SecretRef, SecretRefError, secret_ref

__all__ = [
    "CapabilityDeclaration",
    "CapabilityError",
    "ContractCase",
    "ContractResult",
    "MockAdapter",
    "SecretRef",
    "SecretRefError",
    "declare_capabilities",
    "run_contract_tests",
    "secret_ref",
    "validate_capabilities",
]
