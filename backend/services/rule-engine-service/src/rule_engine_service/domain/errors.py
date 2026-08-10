"""Rule-engine domain errors."""

from __future__ import annotations


class RuleEngineError(Exception):
    def __init__(self, code: str, category: str, message: str):
        super().__init__(message)
        self.code, self.category, self.message = code, category, message


class ValidationError(RuleEngineError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class ConflictError(RuleEngineError):
    def __init__(self, message: str):
        super().__init__("conflict_error", "conflict_error", message)


class NotFoundError(RuleEngineError):
    def __init__(self, message: str):
        super().__init__("not_found", "not_found_error", message)
