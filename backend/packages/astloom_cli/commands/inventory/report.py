"""Build multi-root inventory report (summary + per-root results)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from astloom_cli.commands.graph import _graph_scope, _graph_service
from astloom_cli.commands.inventory.languages import merge_language_rows
from astloom_cli.commands.inventory.processing import processing_context
from astloom_cli.commands.inventory.root import inventory_one_root
from astloom_cli.commands.inventory.util import pct
from astloom_cli.software_paths import require_software_paths


def build_inventory_report(
    _args: argparse.Namespace | None = None,
    *,
    roots: list[Path] | None = None,
    max_files: int | None = None,
    scope: Any | None = None,
) -> dict[str, Any]:
    svc = _graph_service()
    # Scope from identity/env/connect defaults only (inventory uses word modes, not dashed flags).
    if scope is None:
        scope = _graph_scope(
            argparse.Namespace(tenant="", workspace="", project=""),
            with_defaults=True,
        )
    if roots is None:
        roots = [Path(p) for p in require_software_paths(cli_paths=None)]
    else:
        roots = [Path(p).expanduser().resolve() for p in roots]
    if max_files is None:
        max_files = int(getattr(_args, "max_files", None) or 2000) if _args is not None else 2000
    processing = processing_context(svc)
    results = [
        inventory_one_root(
            svc=svc,
            scope=scope,
            root_path=root,
            max_files=max_files,
            processing=processing,
        )
        for root in roots
    ]

    models_used = sorted({m for row in results for m in (row.get("models_used") or [])})
    return {
        "scope": {
            "tenant": scope.tenant_id,
            "workspace": scope.workspace_id,
            "project": scope.project_id,
        },
        "paths": [r["path"] for r in results],
        "processing": processing,
        "models_used": models_used,
        "totals": _sum_totals(results),
        "languages": merge_language_rows(results),
        "summary": {
            "code": _sum_status(results, "code"),
            "docs": _sum_status(results, "docs"),
            "llm": _sum_llm(results),
            "embeddings": _sum_embeddings(results),
        },
        "results": results,
    }


def _sum_status(results: list[dict[str, Any]], key: str) -> dict[str, int | float]:
    done = 0
    edited = 0
    remaining = 0
    for row in results:
        block = row[key]
        done += int(block.get("done_count") or 0)
        edited += int(block.get("edited_count") or 0)
        remaining += int(block.get("remaining_count") or 0)
    total = done + edited + remaining
    return {
        "done_count": done,
        "edited_count": edited,
        "remaining_count": remaining,
        "total": total,
        "percent_done": pct(done, total),
        "percent_edited": pct(edited, total),
        "percent_remaining": pct(remaining, total),
    }


def _sum_llm(results: list[dict[str, Any]]) -> dict[str, int | float]:
    done = 0
    remaining = 0
    for row in results:
        block = row["code"]["llm"]
        done += int(block["done_count"])
        remaining += int(block["remaining_count"])
    total = done + remaining
    return {
        "done_count": done,
        "remaining_count": remaining,
        "total": total,
        "percent_done": pct(done, total),
    }


def _sum_totals(results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "code_files": sum(int((r.get("totals") or {}).get("code_files") or 0) for r in results),
        "code_bytes": sum(int((r.get("totals") or {}).get("code_bytes") or 0) for r in results),
        "docs_files": sum(int((r.get("totals") or {}).get("docs_files") or 0) for r in results),
        "docs_bytes": sum(int((r.get("totals") or {}).get("docs_bytes") or 0) for r in results),
    }


def _sum_embeddings(results: list[dict[str, Any]]) -> dict[str, int | float]:
    eligible = sum(
        int(((row.get("code") or {}).get("embeddings") or {}).get("eligible_symbols") or 0)
        for row in results
    )
    indexed = sum(
        int(((row.get("code") or {}).get("embeddings") or {}).get("indexed_symbols") or 0)
        for row in results
    )
    missing = sum(
        int(((row.get("code") or {}).get("embeddings") or {}).get("missing_symbols") or 0)
        for row in results
    )
    return {
        "eligible_symbols": eligible,
        "indexed_symbols": indexed,
        "missing_symbols": missing,
        "coverage_percent": round(100.0 * indexed / eligible, 1) if eligible else 100.0,
    }
