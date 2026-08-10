"""WeightProfile catalog + activation/rollback governance (GAP-006)."""

from __future__ import annotations

from .governance import (
    WeightProfileError,
    activate_profile,
    get_active_profile_id,
    list_profiles,
    load_profile,
    rollback_profile,
    validate_profile,
)

__all__ = [
    "WeightProfileError",
    "activate_profile",
    "get_active_profile_id",
    "list_profiles",
    "load_profile",
    "rollback_profile",
    "validate_profile",
]
