"""Mock adapter fixture for harness contract tests."""

from __future__ import annotations

from typing import Any

from ..capability import CapabilityDeclaration, declare_capabilities
from ..secret_ref import SecretRef, secret_ref


class MockAdapter:
    """In-memory adapter used as the default contract-test fixture."""

    def __init__(
        self,
        *,
        adapter_id: str = "mock.adapter",
        version: str = "1.0.0",
        capabilities: list[str] | None = None,
        secret_names: list[str] | None = None,
    ) -> None:
        self._declaration = declare_capabilities(
            adapter_id,
            version,
            capabilities or ["health.check", "echo"],
        )
        self._secrets = [secret_ref(n) for n in (secret_names or ["mock.api_token"])]
        self.invocations: list[tuple[str, dict[str, Any]]] = []

    def declare(self) -> CapabilityDeclaration:
        return self._declaration

    def secret_refs(self) -> list[SecretRef]:
        return list(self._secrets)

    def invoke(self, capability: str, payload: dict[str, Any]) -> dict[str, Any]:
        if capability not in self._declaration.capabilities:
            raise KeyError(f"unsupported capability: {capability}")
        self.invocations.append((capability, dict(payload)))
        if capability == "echo":
            return {"echo": payload}
        return {"ok": True, "capability": capability}
