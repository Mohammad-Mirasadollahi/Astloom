"""Typed memory-service errors."""

from __future__ import annotations


class MemoryError(Exception):
    def __init__(self, code: str, category: str, message: str):
        super().__init__(message)
        self.code = code
        self.category = category
        self.message = message


class ValidationError(MemoryError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class ConflictError(MemoryError):
    def __init__(self, message: str):
        super().__init__("conflict_error", "conflict_error", message)


class NotFoundError(MemoryError):
    def __init__(self, message: str):
        super().__init__("not_found", "not_found_error", message)
