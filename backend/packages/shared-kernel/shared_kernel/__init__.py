"""Shared-kernel primitives: results, errors, time, validation, config loaders."""

from .config import (
    ConfigError,
    load_environment_profile,
    load_technology_profile,
    validate_environment_profile,
    validate_technology_profile,
)
from .errors import AppError, ERROR_CATEGORIES
from .results import Err, Ok, Result, is_err, is_ok
from .time import Clock, FakeClock, SystemClock
from .validation import require_fields, require_mapping, require_non_empty_str

__all__ = [
    "AppError",
    "Clock",
    "ConfigError",
    "ERROR_CATEGORIES",
    "Err",
    "FakeClock",
    "Ok",
    "Result",
    "SystemClock",
    "is_err",
    "is_ok",
    "load_environment_profile",
    "load_technology_profile",
    "require_fields",
    "require_mapping",
    "require_non_empty_str",
    "validate_environment_profile",
    "validate_technology_profile",
]
