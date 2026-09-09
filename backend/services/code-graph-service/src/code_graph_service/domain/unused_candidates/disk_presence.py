"""Fail-closed checks: graph symbols that no longer exist on disk are not deletable claims."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def demote_rows_missing_on_disk(
    candidates: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    *,
    repo_root: str,
    include_uncertain: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Demote safe_to_delete when the file is gone or the symbol name is absent from disk.

    Only call when *repo_root* is the indexed software tree (project pin), not the
    Astloom install root — otherwise relative paths from other projects false-demote.
    """
    root = Path(repo_root).expanduser()
    try:
        if not root.is_dir():
            return candidates, skipped
    except OSError:
        return candidates, skipped

    still_safe: list[dict[str, Any]] = []
    for row in candidates:
        if not row.get("safe_to_delete"):
            still_safe.append(row)
            continue
        reason = _missing_reason(root, row)
        if not reason:
            still_safe.append(row)
            continue
        demoted = dict(row)
        demoted["safe_to_delete"] = False
        blockers = list(demoted.get("blockers") or [])
        blockers = list(dict.fromkeys([*blockers, reason]))
        demoted["blockers"] = blockers
        if include_uncertain or blockers:
            skipped.append(demoted)
        # else drop — never surface as safe

    return still_safe, skipped


def _missing_reason(root: Path, row: dict[str, Any]) -> str | None:
    rel = str(row.get("path") or "").strip().replace("\\", "/")
    if not rel or rel.startswith("/"):
        return None
    path = root / rel
    try:
        if not path.is_file():
            return "disk_file_missing"
    except OSError:
        return "disk_file_unreadable"
    name = str(row.get("symbol") or "").strip()
    if not name or row.get("finding_kind") in {
        "unreachable_file",
        "zombie_package",
        "unwired_shared_package",
        "dead_subgraph",
    }:
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "disk_file_unreadable"
    if name not in text:
        return "disk_symbol_absent"
    return None
