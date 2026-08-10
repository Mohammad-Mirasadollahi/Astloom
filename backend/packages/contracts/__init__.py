"""Shared public API and event contract helpers."""

from .api import (
    ERROR_CATEGORIES,
    ContractError,
    make_error_envelope,
    make_page,
    validate_error_envelope,
    validate_page,
)
from .events import (
    REQUIRED_ENVELOPE_FIELDS,
    make_event_envelope,
    validate_event_envelope,
)

__all__ = [
    "ERROR_CATEGORIES",
    "ContractError",
    "REQUIRED_ENVELOPE_FIELDS",
    "make_error_envelope",
    "make_event_envelope",
    "make_page",
    "validate_error_envelope",
    "validate_event_envelope",
    "validate_page",
]
