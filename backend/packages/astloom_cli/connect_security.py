"""Security helpers and safe config I/O for `astloom connect`."""

from __future__ import annotations

import os
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from astloom_cli.connect_config import ConnectSettings


@contextmanager
def file_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        yield
        return
    import fcntl

    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_write_text(path: Path, content: str, *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(content, encoding="utf-8")
        if sys.platform != "win32":
            os.chmod(tmp, mode)
        tmp.replace(path)
        if sys.platform != "win32":
            os.chmod(path, mode)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def harden_connect_config_permissions(path: Path) -> None:
    if sys.platform == "win32":
        return
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def validate_connect_settings(settings: "ConnectSettings") -> list[str]:
    """Return non-fatal security warnings."""
    warnings: list[str] = []
    if settings.api_token and len(settings.api_token) < 16:
        warnings.append("security: API token looks short; use a strong random token")
    return warnings


def reject_secrets_in_connect_doc(doc: dict[str, Any], path: Path) -> None:
    auth = doc.get("auth") or {}
    forbidden = ("password", "postgres_password", "neo4j_password", "secret")
    for key in forbidden:
        if key in auth and str(auth[key]).strip():
            raise SystemExit(
                f"error: do not store {key!r} in {path}; use auth.token_env + environment"
            )
    if str(auth.get("token") or "").strip() and str(auth.get("token_env") or "").strip():
        raise SystemExit(f"error: use either auth.token_env or inline token in {path}, not both")


def merge_lock_path(config_path: Path) -> Path:
    return config_path.parent / ".astloom-connect-merge.lock"
