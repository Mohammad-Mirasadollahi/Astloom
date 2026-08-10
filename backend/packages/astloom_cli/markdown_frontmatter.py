"""Parse Markdown YAML frontmatter for human-doc sync (Phase 2)."""

from __future__ import annotations

import re
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def _json_safe_frontmatter_value(value: Any) -> Any:
    """Normalize YAML scalars so MCP/JSON consumers never see date objects."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe_frontmatter_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_frontmatter_value(v) for v in value]
    return value


def parse_markdown_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return ``(frontmatter, body)``. Missing/invalid YAML yields empty frontmatter."""
    raw = text if isinstance(text, str) else str(text or "")
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return {}, raw
    try:
        loaded = yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}, raw
    if not isinstance(loaded, dict):
        return {}, raw
    return {str(k): _json_safe_frontmatter_value(v) for k, v in loaded.items()}, match.group(2)


def provisional_frontmatter(
    relative_path: str,
    body: str,
    partial: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fill Full-tier required fields for Body-tier docs (index without graph edges)."""
    fm = dict(partial or {})
    path = relative_path.replace("\\", "/")
    if not str(fm.get("doc_id") or "").strip():
        fm["doc_id"] = "doc-" + sha256(path.encode("utf-8")).hexdigest()[:16]
    if not str(fm.get("title") or "").strip():
        title = ""
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                break
        stem = Path(path).stem or path
        fm["title"] = title or stem
    if not str(fm.get("owner") or "").strip():
        fm["owner"] = "unknown"
    status = str(fm.get("status") or "").strip()
    if status not in {"draft", "active", "deprecated", "archived"}:
        fm["status"] = "draft"
    if not str(fm.get("schema_version") or "").strip():
        fm["schema_version"] = "1.0"
    if not isinstance(fm.get("linked_symbols"), list):
        fm["linked_symbols"] = []
    if not isinstance(fm.get("decision_refs"), list):
        fm["decision_refs"] = []
    if not str(fm.get("canonical_path") or "").strip():
        fm["canonical_path"] = path
    return fm
