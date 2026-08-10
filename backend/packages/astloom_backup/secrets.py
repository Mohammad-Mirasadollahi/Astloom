"""Reject payloads that look like live secrets."""

from __future__ import annotations

import re
from typing import Any

_SECRET_KEY = re.compile(
    r"(password|secret|api[_-]?key|private[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|bearer|credential_material)",
    re.I,
)
_SECRET_VALUE = re.compile(
    r"(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"sk-[A-Za-z0-9]{20,}|"
    r"ghp_[A-Za-z0-9]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,})",
)


def find_secret_hit(obj: Any, *, path: str = "$") -> str | None:
    """Return a path description if *obj* looks like it contains a secret."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_s = str(key)
            if _SECRET_KEY.search(key_s) and value not in (None, "", {}, []):
                # Fingerprints / profiles are allowed metadata.
                if key_s.lower() in {
                    "credential_fingerprint",
                    "auth_profile",
                    "secret_ref",
                }:
                    continue
                return f"{path}.{key_s}"
            hit = find_secret_hit(value, path=f"{path}.{key_s}")
            if hit:
                return hit
        return None
    if isinstance(obj, list):
        for i, item in enumerate(obj):
            hit = find_secret_hit(item, path=f"{path}[{i}]")
            if hit:
                return hit
        return None
    if isinstance(obj, str):
        if _SECRET_VALUE.search(obj):
            return path
        return None
    return None


def assert_no_secrets(obj: Any, *, context: str) -> None:
    hit = find_secret_hit(obj)
    if hit:
        raise ValueError(f"secret-like material rejected in {context}: {hit}")
