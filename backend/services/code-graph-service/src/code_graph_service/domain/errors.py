"""Typed errors for the Code-Knowledge Graph domain."""

from __future__ import annotations


class CodeGraphError(Exception):
    def __init__(self, code: str, category: str, message: str):
        super().__init__(message)
        self.code, self.category, self.message = code, category, message


class ValidationError(CodeGraphError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class NotFoundError(CodeGraphError):
    def __init__(self, message: str):
        super().__init__("not_found", "not_found_error", message)


class ConflictError(CodeGraphError):
    def __init__(self, message: str):
        super().__init__("conflict_error", "conflict_error", message)


class ClientDisconnected(CodeGraphError):
    """Raised when the HTTP client closes the connection mid-request."""

    def __init__(self, message: str = "client disconnected during request"):
        super().__init__("client_disconnected", "cancelled", message)


class DatabaseCapacityError(CodeGraphError):
    """Postgres (or pool) refused work because client slots are exhausted."""

    def __init__(
        self,
        message: str = (
            "PostgreSQL has no free client slots (too many clients). "
            "Retry after other Astloom sync/MCP load drops, or raise "
            "max_connections / lower parallel workers."
        ),
    ) -> None:
        super().__init__("database_capacity", "capacity_error", message)
