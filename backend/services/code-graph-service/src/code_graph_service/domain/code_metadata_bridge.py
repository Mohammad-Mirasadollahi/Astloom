"""Build and validate code-metadata contract records for ingest.

Role: map graph FILE/symbol upserts onto the shared ``code_metadata`` contracts.
SoT: ``code_metadata.validate_*`` required fields; records live under symbol.metadata.
Allowed: default repository_id to project_id; soft-attach validation errors.
Forbidden: failing ingest solely because optional doc fields are absent.
"""

from __future__ import annotations

from typing import Any, Mapping

from code_metadata import validate_file_metadata, validate_symbol_metadata

CODE_METADATA_VERSION = "1"


def build_file_metadata_record(
    *,
    file_id: str,
    project_id: str,
    path: str,
    language: str,
    content_hash: str,
    ast_hash: str | None = None,
    repository_id: str | None = None,
    freshness_status: str = "CURRENT",
    confidence_score: float = 0.7,
) -> dict[str, Any]:
    return {
        "file_id": file_id,
        "project_id": project_id,
        "repository_id": (repository_id or project_id).strip() or project_id,
        "path": path,
        "language": language,
        "content_hash": content_hash,
        "ast_hash": ast_hash or content_hash,
        "freshness_status": freshness_status,
        "confidence_score": confidence_score,
    }


def build_symbol_metadata_record(
    *,
    symbol_id: str,
    file_id: str,
    qualified_name: str,
    symbol_type: str,
    confidence_score: float = 0.5,
    metadata_version: str = CODE_METADATA_VERSION,
) -> dict[str, Any]:
    return {
        "symbol_id": symbol_id,
        "file_id": file_id,
        "qualified_name": qualified_name,
        "symbol_type": symbol_type,
        "confidence_score": confidence_score,
        "metadata_version": metadata_version,
    }


def merge_code_metadata(
    base: Mapping[str, Any] | None,
    record: Mapping[str, Any],
    *,
    kind: str,
) -> dict[str, Any]:
    """Validate ``record`` and merge into symbol metadata (soft errors)."""
    errors = (
        validate_file_metadata(record)
        if kind == "file"
        else validate_symbol_metadata(record)
    )
    out = dict(base or {})
    out["code_metadata"] = dict(record)
    out["confidence_score"] = record.get("confidence_score")
    if kind == "file":
        out["freshness_status"] = record.get("freshness_status")
        out["risk_tags"] = list(out.get("risk_tags") or [])
    if errors:
        out["code_metadata_errors"] = list(errors)
    else:
        out.pop("code_metadata_errors", None)
    return out
