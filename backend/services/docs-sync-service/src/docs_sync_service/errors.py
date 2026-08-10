"""Typed errors for the docs-sync application boundary."""

from __future__ import annotations


class DocsSyncError(Exception):
    def __init__(self, code: str, category: str, message: str):
        super().__init__(message)
        self.code, self.category, self.message = code, category, message


class ValidationError(DocsSyncError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class ConflictError(DocsSyncError):
    def __init__(self, message: str):
        super().__init__("conflict_error", "conflict_error", message)


class NotFoundError(DocsSyncError):
    def __init__(self, message: str):
        super().__init__("not_found", "not_found_error", message)
