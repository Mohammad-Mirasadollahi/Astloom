"""Contract test runner for adapters.

Role: run declare/validate/invoke cases against an adapter protocol object.
SoT: case list + adapter responses. Failures are collected, not swallowed.
Allowed failure: ContractResult.ok False with error messages. Forbidden: reading secret values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .capability import CapabilityDeclaration, validate_capabilities
from .secret_ref import SecretRef


class AdapterProtocol(Protocol):
    def declare(self) -> CapabilityDeclaration: ...

    def secret_refs(self) -> list[SecretRef]: ...

    def invoke(self, capability: str, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ContractCase:
    name: str
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    invoke_capability: str | None = None
    invoke_payload: dict[str, Any] = field(default_factory=dict)
    expect_ok: bool = True


@dataclass
class ContractResult:
    case: str
    ok: bool
    detail: str = ""


def run_contract_tests(
    adapter: AdapterProtocol,
    cases: list[ContractCase],
) -> list[ContractResult]:
    results: list[ContractResult] = []
    for case in cases:
        try:
            declaration = adapter.declare()
            missing = validate_capabilities(
                declaration, required=case.required_capabilities
            )
            for ref in adapter.secret_refs():
                if not isinstance(ref, SecretRef):
                    raise TypeError("secret_refs must return SecretRef instances")
                payload = ref.to_dict()
                if set(payload.keys()) != {"name"}:
                    raise RuntimeError("secret ref serialization must be name-only")

            if missing:
                detail = f"missing capabilities: {', '.join(missing)}"
                results.append(
                    ContractResult(
                        case=case.name,
                        ok=not case.expect_ok,
                        detail=detail,
                    )
                )
                continue

            if case.invoke_capability:
                out = adapter.invoke(case.invoke_capability, dict(case.invoke_payload))
                if not isinstance(out, dict):
                    raise TypeError("invoke must return a dict")

            results.append(
                ContractResult(
                    case=case.name,
                    ok=case.expect_ok,
                    detail="passed" if case.expect_ok else "expected failure did not occur",
                )
            )
        except Exception as exc:  # noqa: BLE001 — collect per-case failures
            results.append(
                ContractResult(
                    case=case.name,
                    ok=not case.expect_ok,
                    detail=str(exc),
                )
            )
    return results
