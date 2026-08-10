from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ERROR_CATEGORIES = frozenset(
    {
        "validation_error",
        "authentication_error",
        "authorization_error",
        "conflict_error",
        "not_found_error",
        "dependency_error",
        "rate_limit_error",
        "policy_error",
        "internal_error",
    }
)

REQUIRED_ERROR_FIELDS = (
    "error_code",
    "category",
    "message",
    "retryable",
    "correlation_id",
    "details",
    "documentation_ref",
)

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


class ContractError(ValueError):
    pass


def make_error_envelope(
    *,
    error_code: str,
    category: str,
    message: str,
    correlation_id: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
    documentation_ref: str = "",
) -> dict[str, Any]:
    if category not in ERROR_CATEGORIES:
        raise ContractError(f"invalid error category: {category}")
    return {
        "error": {
            "error_code": error_code,
            "category": category,
            "message": message,
            "retryable": retryable,
            "correlation_id": correlation_id,
            "details": details or {},
            "documentation_ref": documentation_ref,
        }
    }


def make_page(
    items: list[Any],
    *,
    page_size: int,
    correlation_id: str,
    next_page_token: str | None = None,
    has_more: bool | None = None,
) -> dict[str, Any]:
    if page_size < 1:
        raise ContractError("page_size must be >= 1")
    more = bool(next_page_token) if has_more is None else has_more
    return {
        "items": list(items),
        "page": {
            "next_page_token": next_page_token,
            "page_size": page_size,
            "has_more": more,
        },
        "correlation_id": correlation_id,
    }


def validate_error_envelope(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    error = payload.get("error")
    if not isinstance(error, dict):
        return ["error object is required"]
    for field in REQUIRED_ERROR_FIELDS:
        if field not in error:
            errors.append(f"error missing {field}")
    category = error.get("category")
    if category is not None and category not in ERROR_CATEGORIES:
        errors.append(f"invalid error category: {category}")
    if "retryable" in error and not isinstance(error.get("retryable"), bool):
        errors.append("retryable must be a boolean")
    if "details" in error and not isinstance(error.get("details"), dict):
        errors.append("details must be an object")
    return errors


def validate_page(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if "items" not in payload or not isinstance(payload.get("items"), list):
        errors.append("items list is required")
    page = payload.get("page")
    if not isinstance(page, dict):
        errors.append("page object is required")
    else:
        if "page_size" not in page or not isinstance(page.get("page_size"), int) or page["page_size"] < 1:
            errors.append("page.page_size must be a positive integer")
        if "has_more" not in page or not isinstance(page.get("has_more"), bool):
            errors.append("page.has_more must be a boolean")
        if "next_page_token" not in page:
            errors.append("page.next_page_token is required (may be null)")
    if not str(payload.get("correlation_id") or "").strip():
        errors.append("correlation_id is required")
    return errors


def load_example(name: str) -> dict[str, Any]:
    path = EXAMPLES_DIR / name
    if not path.is_file():
        raise ContractError(f"example missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ContractError(f"example must be an object: {path}")
    return data
