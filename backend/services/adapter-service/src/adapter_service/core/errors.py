from __future__ import annotations

from typing import Any


class AdapterError(Exception):
    def __init__(self, code: str, category: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code, self.category, self.message = code, category, message
        self.details = details or {}


class ValidationError(AdapterError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class ConflictError(AdapterError):
    def __init__(self, message: str, *, code: str = "conflict_error", details: dict[str, Any] | None = None):
        super().__init__(code, "conflict_error", message, details)


class NotFoundError(AdapterError):
    def __init__(self, message: str):
        super().__init__("not_found", "not_found_error", message)
