"""Detect edited (stale) files that need re-ingest / sync."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from code_graph_service.domain.hashing import content_hash
from code_graph_service.domain.languages import detect_language_from_path


def _parse_updated_at(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def disk_content_hash(abs_path: Path, language: str) -> str | None:
    """Hash on-disk source the same way file ingest does."""
    try:
        text = abs_path.read_text(encoding="utf-8")
    except OSError:
        return None
    lang = (language or "").strip() or detect_language_from_path(str(abs_path)) or "python"
    return str(content_hash(text, lang)["hash"])


def classify_edited_paths(
    *,
    root_path: Path,
    indexed: set[str],
    pending_rels: set[str],
    file_meta: dict[str, dict[str, str]],
    force_hash: bool = True,
) -> dict[str, str]:
    """Return relative_path → edit_reason for files that need re-sync.

    Reasons:
    - ``pending`` — marked pending by freshness / watch
    - ``content_changed`` — on-disk hash differs from stored FILE symbol hash
    - ``missing_on_disk`` — indexed path no longer exists on disk

    By default always compare content hashes when a stored hash exists (mtime
    skip caused false negatives on sshfs / copy / clock skew). Set
    ``force_hash=False`` only for cheap CLI previews.
    """
    edited: dict[str, str] = {}
    for rel in indexed:
        reasons: list[str] = []
        if rel in pending_rels:
            reasons.append("pending")
        meta = file_meta.get(rel) or {}
        stored = str(meta.get("hash") or "").strip()
        abs_path = root_path / rel
        if not abs_path.is_file():
            reasons.append("missing_on_disk")
        elif stored:
            needs_hash = True
            if not force_hash:
                try:
                    mtime = abs_path.stat().st_mtime
                except OSError:
                    mtime = None
                updated = _parse_updated_at(str(meta.get("updated_at") or ""))
                needs_hash = mtime is None or updated is None or mtime > (updated + 1.0)
            if needs_hash:
                disk = disk_content_hash(abs_path, str(meta.get("language") or ""))
                if disk and disk != stored:
                    reasons.append("content_changed")
        if reasons:
            if "missing_on_disk" in reasons:
                edited[rel] = "missing_on_disk"
            elif "content_changed" in reasons:
                edited[rel] = "content_changed"
            else:
                edited[rel] = reasons[0]
    return edited
