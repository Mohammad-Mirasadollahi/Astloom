from __future__ import annotations

from typing import Any, Mapping


def require_non_empty_str(value: Any, field: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{field} must be a non-empty string"]
    return []


def require_mapping(value: Any, field: str) -> list[str]:
    if not isinstance(value, Mapping) or not value:
        return [f"{field} must be a non-empty object"]
    return []


def require_fields(obj: Mapping[str, Any], fields: tuple[str, ...] | list[str]) -> list[str]:
    errors: list[str] = []
    for field in fields:
        if field not in obj:
            errors.append(f"missing field: {field}")
    return errors
