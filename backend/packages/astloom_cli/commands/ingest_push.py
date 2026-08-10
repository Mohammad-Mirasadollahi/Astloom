"""Server-side stdin ingest for client content-push sync."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from astloom_cli.commands.graph import _graph_scope, _graph_service
from astloom_cli.util import now_iso, print_json


def _apply_pushed_docs(svc: Any, scope: Any, docs: list[Any]) -> dict[str, Any]:
    """Upsert human docs from push payload (no on-server tree)."""
    from code_graph_service.domain.errors import ValidationError
    from code_graph_service.domain.path_safety import safe_repo_rel_path

    upserted = 0
    failed = 0
    errors: list[str] = []
    if not isinstance(docs, list):
        raise SystemExit("error: docs must be a list when set")
    for entry in docs:
        if not isinstance(entry, dict):
            failed += 1
            errors.append("docs entry must be an object")
            continue
        try:
            rel = safe_repo_rel_path(str(entry.get("relative_path") or entry.get("file_path") or ""))
            doc_id = str(entry.get("doc_id") or "").strip()
            body = entry.get("body")
            if not isinstance(body, str):
                body = "" if body is None else str(body)
            if not doc_id:
                raise ValidationError("doc_id is required")
            if len(body.encode("utf-8", errors="replace")) > 2_000_000:
                raise ValidationError("doc body exceeds 2_000_000 bytes")
            tokens = entry.get("linked_symbol_tokens")
            if tokens is not None and not isinstance(tokens, list):
                raise ValidationError("linked_symbol_tokens must be a list")
            svc.upsert_human_documentation(
                scope,
                doc_id=doc_id,
                relative_path=rel,
                body=body,
                title=str(entry.get("title") or doc_id),
                linked_symbol_tokens=[str(t) for t in (tokens or []) if str(t).strip()],
            )
            upserted += 1
        except Exception as exc:  # noqa: BLE001 — soft-fail per doc
            failed += 1
            errors.append(str(exc)[:200])
    return {"docs_upserted": upserted, "docs_failed": failed, "errors": errors[:20]}


def cmd_ingest_push(args: argparse.Namespace) -> int:
    """Read one JSON object from stdin and run ``ingest_pushed_sources`` (+ optional docs)."""
    raw = sys.stdin.read()
    if not raw.strip():
        raise SystemExit("error: ingest-push expects a JSON body on stdin")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid ingest-push JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("error: ingest-push JSON must be an object")

    files = payload.get("files")
    if files is None:
        raise SystemExit("error: ingest-push JSON requires files (use [] for prune-only)")
    body: dict[str, Any] = {
        "files": files,
        "include_outcomes": bool(payload.get("include_outcomes", True)),
        "embedding_refresh_mode": str(
            payload.get("embedding_refresh_mode")
            or getattr(args, "embedding_refresh_mode", None)
            or "touched"
        ),
    }
    if "present_paths" in payload:
        body["present_paths"] = payload.get("present_paths")
    if payload.get("max_files") is not None:
        body["max_files"] = payload.get("max_files")
    if payload.get("max_file_bytes") is not None:
        body["max_file_bytes"] = payload.get("max_file_bytes")

    svc = _graph_service()
    scope = _graph_scope(args, with_defaults=True)
    result = svc.ingest_pushed_sources(
        scope,
        "cli-push",
        f"cli-push-{now_iso()}",
        f"cli-push:{scope.project_id}:{now_iso()}",
        body,
    )
    out = result.to_dict() if hasattr(result, "to_dict") else dict(result)
    if "docs" in payload:
        out["docs"] = _apply_pushed_docs(svc, scope, payload.get("docs") or [])
    print_json(out)
    return 1 if int(out.get("files_failed") or 0) or int((out.get("docs") or {}).get("docs_failed") or 0) else 0


def cmd_file_hashes(args: argparse.Namespace) -> int:
    """Print FILE path → content hash map for client-side skip."""
    svc = _graph_service()
    scope = _graph_scope(args, with_defaults=True)
    print_json({"hashes": svc.file_content_hashes(scope)})
    return 0
