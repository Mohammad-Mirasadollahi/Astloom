from __future__ import annotations

from typing import Any, Mapping


FILE_METADATA_REQUIRED = (
    "file_id",
    "project_id",
    "repository_id",
    "path",
    "language",
    "content_hash",
    "ast_hash",
    "freshness_status",
    "confidence_score",
)

SYMBOL_METADATA_REQUIRED = (
    "symbol_id",
    "file_id",
    "qualified_name",
    "symbol_type",
    "confidence_score",
    "metadata_version",
)

ALLOWED_FRESHNESS = frozenset({"CURRENT", "STALE", "PARTIAL", "FAILED", "UNKNOWN"})


def _require_fields(obj: Mapping[str, Any], fields: tuple[str, ...], label: str) -> list[str]:
    errors: list[str] = []
    for field in fields:
        if field not in obj:
            errors.append(f"{label} missing {field}")
            continue
        value = obj.get(field)
        if isinstance(value, str) and not value.strip():
            errors.append(f"{label}.{field} must be non-empty")
    return errors


def validate_file_metadata(record: Mapping[str, Any]) -> list[str]:
    errors = _require_fields(record, FILE_METADATA_REQUIRED, "file_metadata")
    status = str(record.get("freshness_status") or "")
    if status and status not in ALLOWED_FRESHNESS:
        errors.append(f"invalid freshness_status: {status}")
    score = record.get("confidence_score")
    if score is not None and not isinstance(score, (int, float)):
        errors.append("confidence_score must be a number")
    elif isinstance(score, (int, float)) and not (0.0 <= float(score) <= 1.0):
        errors.append("confidence_score must be between 0 and 1")
    return errors


def validate_symbol_metadata(record: Mapping[str, Any]) -> list[str]:
    errors = _require_fields(record, SYMBOL_METADATA_REQUIRED, "symbol_metadata")
    score = record.get("confidence_score")
    if score is not None and not isinstance(score, (int, float)):
        errors.append("confidence_score must be a number")
    elif isinstance(score, (int, float)) and not (0.0 <= float(score) <= 1.0):
        errors.append("confidence_score must be between 0 and 1")
    return errors
