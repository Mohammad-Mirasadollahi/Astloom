"""Filesystem path checks with permission-aware errors."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .errors import ValidationError


def require_directory(root_path: str, *, label: str = "root_path") -> Path:
    """Resolve *root_path* to an existing directory visible to this process."""
    text = str(root_path or "").strip()
    if not text:
        raise ValidationError(f"{label} is required")
    raw = Path(text).expanduser()
    try:
        resolved = raw.resolve()
    except PermissionError as exc:
        raise ValidationError(
            f"{label} is not readable by this process: {raw} (permission denied)"
        ) from exc
    try:
        info = os.stat(resolved)
    except FileNotFoundError as exc:
        raise ValidationError(
            f"{label} does not exist or is not visible to this process: {resolved}"
        ) from exc
    except PermissionError as exc:
        raise ValidationError(
            f"{label} is not readable by this process: {resolved} (permission denied)"
        ) from exc
    if not stat.S_ISDIR(info.st_mode):
        raise ValidationError(f"{label} is not a directory: {resolved}")
    return resolved
