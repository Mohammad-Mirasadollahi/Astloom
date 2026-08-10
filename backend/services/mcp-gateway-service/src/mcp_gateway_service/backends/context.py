"""
Module contract: MCP handlers for native context compression.

Role: Compress bulky payloads; store/retrieve originals under MCP request scope.
SoT/invariants: Uses context_compression package; retrieve fails closed on wrong scope.
Allowed failures: missing payload/handle; below-threshold skip; handle miss → ok=False.
Forbidden: cross-scope retrieve; cloud upload; treating ai-toolstack as product SoT.
"""

from __future__ import annotations

from typing import Any

from . import _paths  # noqa: F401
from .platform import PlatformBackends

from context_compression import compress_payload, default_store, metrics_snapshot


def context_compress(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    del backends, correlation_id  # scope ACL only; in-process store
    payload = arguments.get("payload")
    if payload is None:
        raise ValueError("payload is required")
    text = payload if isinstance(payload, str) else str(payload)
    content_type = str(arguments.get("content_type") or "auto")
    ttl = int(arguments.get("ttl_seconds") if arguments.get("ttl_seconds") is not None else 3600)
    result = compress_payload(text, content_type=content_type)
    handle = None
    if not result.skipped:
        handle = default_store().put(
            text,
            scope=scope,
            content_type=result.content_type,
            lossy=result.lossy,
            ttl_seconds=ttl,
        )
    return {
        **base,
        "ok": True,
        "handle": handle,
        **result.public(),
        "store_entries": default_store().stats()["entries"],
        "metrics": metrics_snapshot(),
    }


def context_retrieve(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    del backends, correlation_id
    handle = str(arguments.get("handle") or "").strip()
    if not handle:
        raise ValueError("handle is required")
    got = default_store().get(handle, scope=scope)
    if got is None:
        return {
            **base,
            "ok": False,
            "error": "handle_not_found_or_wrong_scope",
            "handle": handle,
        }
    return {**base, "ok": True, **got}


def context_stats(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    del backends, arguments, correlation_id
    return {
        **base,
        "ok": True,
        "scope_note": "Counters are process-local to this MCP gateway",
        "request_scope": scope,
        "metrics": metrics_snapshot(),
        "store_entries": default_store().stats()["entries"],
    }
