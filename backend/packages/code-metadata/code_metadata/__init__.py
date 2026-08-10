"""Code metadata contracts and profile loaders."""

from .contracts import (
    FILE_METADATA_REQUIRED,
    SYMBOL_METADATA_REQUIRED,
    validate_file_metadata,
    validate_symbol_metadata,
)
from .loader import (
    CodeMetadataError,
    load_profile,
    should_escalate_to_source,
    validate_profile,
)

__all__ = [
    "CodeMetadataError",
    "FILE_METADATA_REQUIRED",
    "SYMBOL_METADATA_REQUIRED",
    "load_profile",
    "should_escalate_to_source",
    "validate_file_metadata",
    "validate_profile",
    "validate_symbol_metadata",
]
