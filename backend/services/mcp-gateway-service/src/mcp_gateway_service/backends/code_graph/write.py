"""MCP write handlers: ingest, sync, purge."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from code_graph_service.domain.errors import CodeGraphError, NotFoundError

from ..platform import PlatformBackends

def ingest_file(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    file_path = str(arguments.get("file_path") or "").strip()
    source = str(arguments.get("source") or "")
    language = str(arguments.get("language") or "python").strip() or "python"
    if not file_path:
        raise ValueError("file_path is required")
    if not source.strip():
        raise ValueError("source is required")
    idempotency_key = str(arguments.get("idempotency_key") or f"mcp-ingest:{file_path}:{correlation_id}").strip()
    try:
        result = backends.graph.ingest_file(
            backends.graph_scope(scope),
            backends.actor_id,
            correlation_id or str(uuid4()),
            idempotency_key,
            {
                "file_path": file_path,
                "language": language,
                "source": source,
            },
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    if hasattr(result, "public"):
        public = result.public()
    else:
        public = {
            "file_id": result.file_id,
            "symbols_indexed": result.symbols_indexed,
            "symbols_changed": result.symbols_changed,
            "symbols_documented": result.symbols_documented,
            "edges_written": result.edges_written,
            "changed_symbol_ids": list(result.changed_symbol_ids),
        }
    return {
        **base,
        "graph_mode": backends.graph_mode,
        "ingest": public,
    }


def ingest_repo(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    root_path = str(arguments.get("root_path") or "").strip()
    if not root_path:
        raise ValueError("root_path is required")
    payload: dict[str, Any] = {"root_path": root_path}
    if arguments.get("include_extensions") is not None:
        payload["include_extensions"] = arguments.get("include_extensions")
    if arguments.get("exclude_dirs") is not None:
        payload["exclude_dirs"] = arguments.get("exclude_dirs")
    if arguments.get("max_files") is not None:
        payload["max_files"] = int(arguments["max_files"])
    if arguments.get("max_file_bytes") is not None:
        payload["max_file_bytes"] = int(arguments["max_file_bytes"])
    if "include_outcomes" in arguments:
        payload["include_outcomes"] = bool(arguments.get("include_outcomes"))
    idempotency_key = str(
        arguments.get("idempotency_key") or f"mcp-ingest-repo:{root_path}:{correlation_id}"
    ).strip()
    try:
        result = backends.graph.ingest_repo(
            backends.graph_scope(scope),
            backends.actor_id,
            correlation_id or str(uuid4()),
            idempotency_key,
            payload,
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    payload = result.to_dict()
    refresh = payload.get("embedding_refresh") or {}
    ok = int(payload.get("files_failed") or 0) == 0 and refresh.get("state") != "failed"
    return {
        **base,
        "ok": ok,
        "graph_mode": backends.graph_mode,
        "ingest_repo": payload,
    }


def sync_repo(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    from pathlib import Path

    root_path = str(arguments.get("root_path") or "").strip()
    if not root_path:
        raise ValueError("root_path is required")
    payload: dict[str, Any] = {"root_path": root_path, "include_outcomes": True}
    if arguments.get("max_files") is not None:
        payload["max_files"] = int(arguments["max_files"])
    refresh_mode = str(arguments.get("embedding_refresh_mode") or "").strip().lower()
    if refresh_mode in {"touched", "full"}:
        payload["embedding_refresh_mode"] = refresh_mode
    if arguments.get("include_extensions") is not None:
        payload["include_extensions"] = arguments.get("include_extensions")
    else:
        # Same operator filters as CLI `astloom sync` (astloom.sync.yaml).
        try:
            from astloom_cli.sync_config import SyncConfigError, resolve_sync_filters

            filters = resolve_sync_filters(root=Path(root_path), require_config=False)
            payload["include_extensions"] = filters["include_extensions"]
            payload["exclude_dirs"] = filters["exclude_dirs"]
            payload["exclude_globs"] = filters["exclude_globs"]
            if filters.get("include_paths"):
                payload["include_path_prefixes"] = filters["include_paths"]
        except (SyncConfigError, SystemExit, OSError, ValueError) as exc:
            payload.setdefault("_filter_warning", str(exc)[:200])
        except Exception as exc:  # noqa: BLE001 — fall back to discovery defaults
            payload.setdefault("_filter_warning", str(exc)[:200])
    idempotency_key = str(
        arguments.get("idempotency_key") or f"mcp-sync:{root_path}:{correlation_id}"
    ).strip()
    try:
        result = backends.graph.sync_repo(
            backends.graph_scope(scope),
            backends.actor_id,
            correlation_id or str(uuid4()),
            idempotency_key,
            payload,
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    sync_payload = result.to_dict()
    if payload.get("embedding_refresh_mode"):
        sync_payload["embedding_refresh_mode"] = payload["embedding_refresh_mode"]
    return {
        **base,
        "graph_mode": backends.graph_mode,
        "sync": sync_payload,
    }


def purge_scope(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    if not bool(arguments.get("confirm")):
        raise ValueError("purge requires confirm=true")
    try:
        result = backends.graph.purge_scope(backends.graph_scope(scope))
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, "purge": result}


def _position_args(arguments: dict[str, Any]) -> tuple[str, str, int, int, str]:
    root_path = str(arguments.get("root_path") or "").strip()
    file_path = str(arguments.get("file_path") or "").strip()
    if not root_path or not file_path:
        raise ValueError("root_path and file_path are required")
    line = int(arguments.get("line") if arguments.get("line") is not None else -1)
    character = int(arguments.get("character") if arguments.get("character") is not None else -1)
    if line < 0 or character < 0:
        raise ValueError("line and character are required (0-based)")
    language = str(arguments.get("language") or "").strip()
    return root_path, file_path, line, character, language


def ide_references(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    """IDE-semantic find-references (LSP). Not durable graph neighbors."""
    _ = scope
    root_path, file_path, line, character, language = _position_args(arguments)
    try:
        payload = backends.graph.ide_references(
            root_path=root_path,
            file_path=file_path,
            line=line,
            character=character,
            language=language,
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}


def ide_definition(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    """IDE-semantic go-to-definition (LSP). Not durable graph edges."""
    _ = scope
    root_path, file_path, line, character, language = _position_args(arguments)
    try:
        payload = backends.graph.ide_definition(
            root_path=root_path,
            file_path=file_path,
            line=line,
            character=character,
            language=language,
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}


def ide_rename(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    """IDE-semantic rename (LSP) then AST reconcile_after_edit. Never dual-writes CODE_REL."""
    root_path, file_path, line, character, language = _position_args(arguments)
    new_name = str(arguments.get("new_name") or "").strip()
    if not new_name:
        raise ValueError("new_name is required")
    apply = bool(arguments.get("apply", True))
    run_sync = bool(arguments.get("run_sync", True))
    try:
        payload = backends.graph.ide_rename(
            root_path=root_path,
            file_path=file_path,
            line=line,
            character=character,
            new_name=new_name,
            language=language,
            apply=apply,
            scope=backends.graph_scope(scope),
            actor_id=backends.actor_id,
            correlation_id=correlation_id or str(uuid4()),
            idempotency_key=str(arguments.get("idempotency_key") or f"mcp-ide-rename:{correlation_id}"),
            run_sync=run_sync,
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}


def reconcile_after_edit(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    """Mark edited paths pending; optional AST sync_repo (ADR 48)."""
    paths = arguments.get("file_paths") or []
    if not isinstance(paths, list) or not paths:
        single = str(arguments.get("file_path") or "").strip()
        paths = [single] if single else []
    if not paths:
        raise ValueError("file_paths or file_path is required")
    run_sync = bool(arguments.get("run_sync", False))
    root_path = str(arguments.get("root_path") or "").strip() or None
    try:
        payload = backends.graph.reconcile_after_edit(
            [str(p) for p in paths],
            scope=backends.graph_scope(scope) if run_sync else None,
            root_path=root_path,
            actor_id=backends.actor_id,
            correlation_id=correlation_id or str(uuid4()),
            idempotency_key=str(arguments.get("idempotency_key") or f"mcp-reconcile:{correlation_id}"),
            run_sync=run_sync,
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}
