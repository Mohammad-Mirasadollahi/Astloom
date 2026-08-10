"""Path safety and workspace text-edit application for LSP WorkspaceEdit."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from ..errors import ValidationError


def resolve_under_root(root_path: str, file_path: str) -> tuple[str, Path]:
    """Return (relative posix path, absolute Path) if file_path stays under root."""
    root = Path(root_path).expanduser().resolve()
    if not root.is_dir():
        raise ValidationError(f"root_path is not a directory: {root}")
    raw = (file_path or "").strip().replace("\\", "/")
    if not raw:
        raise ValidationError("file_path is required")
    candidate = Path(raw)
    abs_path = candidate.resolve() if candidate.is_absolute() else (root / raw).resolve()
    try:
        rel = abs_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValidationError(f"file_path escapes root_path: {file_path}") from exc
    return rel, abs_path


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def uri_to_path(uri: str, root: Path) -> Path:
    text = (uri or "").strip()
    if text.startswith("file://"):
        parsed = urlparse(text)
        return Path(unquote(parsed.path))
    return (root / text).resolve()


def apply_workspace_edit(root_path: str, workspace_edit: dict[str, Any]) -> list[str]:
    """Apply LSP WorkspaceEdit changes/documentChanges under root. Returns relative paths."""
    root = Path(root_path).expanduser().resolve()
    changed: list[str] = []
    changes = workspace_edit.get("changes") or {}
    if isinstance(changes, dict):
        for uri, edits in changes.items():
            path = uri_to_path(str(uri), root)
            rel, abs_path = resolve_under_root(str(root), str(path))
            _apply_text_edits(abs_path, list(edits or []))
            changed.append(rel)
    for item in workspace_edit.get("documentChanges") or []:
        if not isinstance(item, dict) or "textDocument" not in item:
            continue
        uri = str((item.get("textDocument") or {}).get("uri") or "")
        path = uri_to_path(uri, root)
        rel, abs_path = resolve_under_root(str(root), str(path))
        _apply_text_edits(abs_path, list(item.get("edits") or []))
        changed.append(rel)
    seen: set[str] = set()
    ordered: list[str] = []
    for rel in changed:
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)
    return ordered


def _position_offset(text: str, line: int, character: int) -> int:
    parts = text.split("\n")
    if line < 0:
        return 0
    if line >= len(parts):
        return len(text)
    prefix = sum(len(p) + 1 for p in parts[:line])
    return prefix + min(max(character, 0), len(parts[line]))


def _apply_text_edits(path: Path, edits: list[Any]) -> None:
    if not path.is_file():
        raise ValidationError(f"cannot apply edit; file missing: {path}")
    text = path.read_text(encoding="utf-8")
    normalized: list[tuple[int, int, int, int, str]] = []
    for edit in edits:
        if not isinstance(edit, dict):
            continue
        rng = edit.get("range") or {}
        start = rng.get("start") or {}
        end = rng.get("end") or {}
        normalized.append(
            (
                int(start.get("line") or 0),
                int(start.get("character") or 0),
                int(end.get("line") or 0),
                int(end.get("character") or 0),
                str(edit.get("newText") or ""),
            )
        )
    normalized.sort(key=lambda t: (t[0], t[1], t[2], t[3]), reverse=True)
    for start_line, start_char, end_line, end_char, new_text in normalized:
        start = _position_offset(text, start_line, start_char)
        end = _position_offset(text, end_line, end_char)
        if end < start:
            end = start
        text = text[:start] + new_text + text[end:]
    path.write_text(text, encoding="utf-8")
