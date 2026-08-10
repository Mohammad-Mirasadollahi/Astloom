"""Adapter capability declaration and validation.

Role: declare adapter capability maps and validate required ids fail-closed.
SoT: CapabilityDeclaration fields from the adapter author; required set from harness caller.
Allowed failure: CapabilityError on empty/invalid declarations. Forbidden: accepting secret values.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class CapabilityError(ValueError):
    pass


@dataclass(frozen=True)
class CapabilityDeclaration:
    adapter_id: str
    version: str
    capabilities: frozenset[str] = field(default_factory=frozenset)

    def to_dict(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "version": self.version,
            "capabilities": sorted(self.capabilities),
        }


def declare_capabilities(
    adapter_id: str,
    version: str,
    capabilities: list[str] | set[str] | frozenset[str],
) -> CapabilityDeclaration:
    aid = (adapter_id or "").strip()
    ver = (version or "").strip()
    if not aid:
        raise CapabilityError("adapter_id is required")
    if not ver:
        raise CapabilityError("version is required")
    caps = frozenset(str(c).strip() for c in capabilities if str(c).strip())
    if not caps:
        raise CapabilityError("at least one capability is required")
    return CapabilityDeclaration(adapter_id=aid, version=ver, capabilities=caps)


def validate_capabilities(
    declaration: CapabilityDeclaration,
    *,
    required: list[str] | set[str] | frozenset[str],
) -> list[str]:
    """Return sorted missing required capability ids (empty = ok). Fail-closed listing."""
    need = frozenset(str(c).strip() for c in required if str(c).strip())
    missing = sorted(need - declaration.capabilities)
    return missing
