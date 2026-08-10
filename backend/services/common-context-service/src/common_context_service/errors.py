"""Typed errors for common-context-service."""

from __future__ import annotations


class CommonContextError(Exception):
    def __init__(self, code: str, category: str, message: str):
        super().__init__(message)
        self.code, self.category, self.message = code, category, message


class ValidationError(CommonContextError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class ConflictError(CommonContextError):
    def __init__(self, message: str):
        super().__init__("conflict_error", "conflict_error", message)


class NotFoundError(CommonContextError):
    def __init__(self, message: str):
        super().__init__("not_found", "not_found_error", message)
