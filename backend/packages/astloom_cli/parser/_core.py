"""Shared argparse helpers for the astloom CLI parser package."""

from __future__ import annotations

import argparse
import sys

_SYNC_MAX_FILE_DASHED = frozenset({"-max-file", "--max-file", "-max-files", "--max-files"})
# Soft default: 0 = auto (discover up to HARD_SYNC_MAX_FILES). Explicit ``max-file N`` caps.
HARD_SYNC_MAX_FILES = 20_000
DEFAULT_SYNC_MAX_FILES = 0


def resolve_discovery_max_files(raw: object) -> int:
    """Return discovery cap. ``<=0`` / unset → auto full tree up to ``HARD_SYNC_MAX_FILES``."""
    try:
        n = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return HARD_SYNC_MAX_FILES
    return max(1, min(n, HARD_SYNC_MAX_FILES))


def max_files_is_auto(raw: object) -> bool:
    try:
        return int(raw) <= 0  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True


def peel_sync_words(
    argv: list[str], error
) -> tuple[list[str], int | None, str | None, str | None]:
    """Peel sync word args: ``max-file N``, ``heal``, and ``jobs [job_id]``."""
    if not argv or argv[0] != "sync":
        return argv, None, None, None
    out: list[str] = []
    override: int | None = None
    sync_mode: str | None = None
    sync_job_id: str | None = None
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "heal":
            sync_mode = "heal"
            i += 1
            continue
        if tok == "jobs":
            sync_mode = "jobs"
            i += 1
            if i < len(argv) and not str(argv[i]).startswith("-"):
                sync_job_id = str(argv[i]).strip()
                i += 1
            continue
        if tok in _SYNC_MAX_FILE_DASHED or tok == "max-file":
            label = "max-file" if tok == "max-file" else tok.lstrip("-")
            if i + 1 >= len(argv):
                error(f"argument {label}: expected one integer argument")
            try:
                override = int(argv[i + 1])
            except ValueError:
                error(f"argument {label}: invalid int value: {argv[i + 1]!r}")
            if override < 1:
                error(f"argument {label}: must be >= 1 (got {override})")
            i += 2
            continue
        out.append(tok)
        i += 1
    return out, override, sync_mode, sync_job_id


class AstloomArgumentParser(argparse.ArgumentParser):
    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            args = sys.argv[1:]
        args, max_files_override, sync_mode, sync_job_id = peel_sync_words(
            list(args), self.error
        )
        ns, rest = super().parse_known_args(args, namespace)
        if max_files_override is not None:
            ns.max_files = max_files_override
        if sync_mode is not None:
            ns.sync_mode = sync_mode
        if sync_job_id is not None:
            ns.sync_job_id = sync_job_id
        return ns, rest
