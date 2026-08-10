"""Rewrite scope fields and embedded / plain row ids in exported rows."""

from __future__ import annotations

from typing import Any

from astloom_backup.scope import Remap, Scope

_ID_KEYS = ("id", "symbol_id", "from_id", "to_id", "source_id", "target_id", "memory_id")
_EMBEDDED_PREFIXES = ("sym:", "doc:", "edge:")
_PLAIN_MARKER = "asbak:"


def remap_row(row: dict[str, Any], *, source: Scope, target: Scope) -> dict[str, Any]:
    out = dict(row)
    if "tenant_id" in out and out["tenant_id"] == source.tenant_id:
        out["tenant_id"] = target.tenant_id
    if "workspace_id" in out and out["workspace_id"] == source.workspace_id:
        out["workspace_id"] = target.workspace_id
    if "project_id" in out and out["project_id"] == source.project_id:
        out["project_id"] = target.project_id
    # Symbol / doc ids embed project_id: sym:{project}:… / doc:{project}:…
    # Plain text PKs (memory/common_context/…) must also change on remap so
    # same-server clone does not collide with the still-present source rows.
    for key in _ID_KEYS:
        if key in out and isinstance(out[key], str):
            out[key] = _remap_id_value(out[key], source=source, target=target)
    # Nested JSON may contain scope or id strings.
    for key, value in list(out.items()):
        if isinstance(value, (dict, list)):
            out[key] = _remap_json(value, source=source, target=target)
    return out


def _same_scope(source: Scope, target: Scope) -> bool:
    return (
        source.tenant_id == target.tenant_id
        and source.workspace_id == target.workspace_id
        and source.project_id == target.project_id
    )


def _remap_embedded_id(value: str, old_project: str, new_project: str) -> str:
    if old_project == new_project:
        return value
    for prefix in _EMBEDDED_PREFIXES:
        needle = f"{prefix}{old_project}:"
        if value.startswith(needle):
            return f"{prefix}{new_project}:" + value[len(needle) :]
    return value


def _plain_id_marker(target: Scope) -> str:
    return (
        f"{_PLAIN_MARKER}{target.tenant_id}/"
        f"{target.workspace_id}/{target.project_id}:"
    )


def _remap_plain_id(value: str, *, source: Scope, target: Scope) -> str:
    """Namespace opaque text PKs when scope changes (deterministic, reversible strip)."""
    if _same_scope(source, target) or not value:
        return value
    marker = _plain_id_marker(target)
    if value.startswith(marker):
        return value
    if value.startswith(_PLAIN_MARKER):
        # Remap again: keep payload after the third slash-segment marker.
        _, _, rest = value.partition(":")
        # rest = "t/w/p:original"
        parts = rest.split(":", 1)
        value = parts[1] if len(parts) == 2 else value
    return marker + value


def _remap_id_value(value: str, *, source: Scope, target: Scope) -> str:
    embedded = _remap_embedded_id(value, source.project_id, target.project_id)
    if embedded != value:
        return embedded
    return _remap_plain_id(value, source=source, target=target)


def _remap_json(obj: Any, *, source: Scope, target: Scope) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in _ID_KEYS and isinstance(v, str):
                out[k] = _remap_id_value(v, source=source, target=target)
            else:
                out[k] = _remap_json(v, source=source, target=target)
        return out
    if isinstance(obj, list):
        return [_remap_json(v, source=source, target=target) for v in obj]
    if isinstance(obj, str):
        if obj == source.tenant_id:
            return target.tenant_id
        if obj == source.workspace_id:
            return target.workspace_id
        if obj == source.project_id:
            return target.project_id
        # Free-form JSON strings: only rewrite embedded sym:/doc:/edge: ids.
        # Opaque PK namespacing stays on known id columns (see remap_row).
        return _remap_embedded_id(obj, source.project_id, target.project_id)
    return obj


def resolve_target_scope(source: Scope, remap: Remap | None) -> Scope:
    if remap is None or not remap.active:
        return source
    return remap.apply(source)
