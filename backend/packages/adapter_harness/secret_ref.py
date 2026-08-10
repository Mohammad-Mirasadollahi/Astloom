"""Secret references by name only — never carry values.

Role: name-only secret handle for adapter config.
SoT: SecretRef.name is the only field; values live in the host secrets plane.
Allowed failure: SecretRefError on empty/invalid names. Forbidden: storing secret values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")


class SecretRefError(ValueError):
    pass


@dataclass(frozen=True)
class SecretRef:
    """Reference a secret by name. Never includes a value field."""

    name: str

    def __post_init__(self) -> None:
        cleaned = (self.name or "").strip()
        if not cleaned:
            raise SecretRefError("secret name is required")
        if "=" in cleaned or not _NAME_RE.match(cleaned):
            raise SecretRefError(f"invalid secret name: {cleaned!r}")
        object.__setattr__(self, "name", cleaned)

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name}


def secret_ref(name: str) -> SecretRef:
    """Construct a name-only SecretRef (never accepts a value)."""
    return SecretRef(name=name)
