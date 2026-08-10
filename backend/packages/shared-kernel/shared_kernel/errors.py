from __future__ import annotations

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


class AppError(Exception):
    """Typed application error with a public API envelope shape."""

    def __init__(
        self,
        error_code: str,
        category: str,
        message: str,
        *,
        retryable: bool = False,
        correlation_id: str = "",
        details: dict[str, Any] | None = None,
        documentation_ref: str = "",
    ) -> None:
        super().__init__(message)
        if category not in ERROR_CATEGORIES:
            raise ValueError(f"invalid error category: {category}")
        self.error_code = error_code
        self.category = category
        self.message = message
        self.retryable = retryable
        self.correlation_id = correlation_id
        self.details = details or {}
        self.documentation_ref = documentation_ref

    def to_public(self) -> dict[str, Any]:
        return {
            "error": {
                "error_code": self.error_code,
                "category": self.category,
                "message": self.message,
                "retryable": self.retryable,
                "correlation_id": self.correlation_id,
                "details": self.details,
                "documentation_ref": self.documentation_ref,
            }
        }
