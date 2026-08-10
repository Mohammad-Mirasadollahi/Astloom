"""Safe repository-relative paths for client content-push ingest.

Role: reject absolute paths, traversal, and null bytes before graph keys are written.
SoT: POSIX-normalized relative paths under a virtual repo root (never disk-resolved).
Allowed: empty → ValidationError; callers soft-fail or fail closed.
Forbidden: accepting ``..``, absolute paths, or NUL in path segments.
"""

from __future__ import annotations

from .errors import ValidationError

DEFAULT_MAX_REL_PATH_LEN = 1024


def safe_repo_rel_path(
    raw: str,
    *,
    max_len: int = DEFAULT_MAX_REL_PATH_LEN,
) -> str:
    """Normalize to a POSIX relative path or raise ``ValidationError``."""
    text = str(raw or "").replace("\\", "/").strip()
    if not text:
        raise ValidationError("relative path is required")
    if "\x00" in text:
        raise ValidationError("relative path must not contain NUL")
    if text.startswith("/") or text.startswith("~"):
        raise ValidationError(f"absolute path rejected: {text[:80]}")
    # Windows drive / UNC
    if len(text) >= 2 and text[1] == ":":
        raise ValidationError(f"absolute path rejected: {text[:80]}")
    if text.startswith("//"):
        raise ValidationError(f"absolute path rejected: {text[:80]}")

    parts: list[str] = []
    for part in text.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ValidationError(f"path traversal rejected: {text[:80]}")
        parts.append(part)
    if not parts:
        raise ValidationError("relative path is required")
    out = "/".join(parts)
    if len(out) > max_len:
        raise ValidationError(f"relative path exceeds {max_len} characters")
    return out
