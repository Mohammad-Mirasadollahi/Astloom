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
) -> dict[str, str]:
    """Return relative_path → edit_reason for files that need re-sync.

    Reasons:
    - ``pending`` — marked pending by freshness / watch
    - ``content_changed`` — on-disk hash differs from stored FILE symbol hash

    Fast path: skip hashing when file mtime is not newer than symbol ``updated_at``.
    """
    edited: dict[str, str] = {}
    for rel in indexed:
        reasons: list[str] = []
        if rel in pending_rels:
            reasons.append("pending")
        meta = file_meta.get(rel) or {}
        stored = str(meta.get("hash") or "").strip()
        abs_path = root_path / rel
        if stored:
            try:
                mtime = abs_path.stat().st_mtime
            except OSError:
                mtime = None
            updated = _parse_updated_at(str(meta.get("updated_at") or ""))
            # Only read+hash when mtime is missing/newer, or updated_at unknown.
            needs_hash = mtime is None or updated is None or mtime > (updated + 1.0)
            if needs_hash:
                disk = disk_content_hash(abs_path, str(meta.get("language") or ""))
                if disk and disk != stored:
                    reasons.append("content_changed")
        if reasons:
            edited[rel] = "content_changed" if "content_changed" in reasons else reasons[0]
    return edited
