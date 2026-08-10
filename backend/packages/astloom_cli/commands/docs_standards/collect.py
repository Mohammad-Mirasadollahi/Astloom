"""Scan docs trees and build a standards compliance report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astloom_cli.commands.docs_standards.check import check_file
from astloom_cli.docs_audit_scope import (
    DEFAULT_DOC_ROOTS,
    is_docs_audit_path,
    normalize_repo_rel,
)
from astloom_cli.commands.inventory.util import TOP_N, pct, top
from astloom_cli.util import repo_root

__all__ = ["DEFAULT_DOC_ROOTS", "build_docs_standards_report"]


def _iter_markdown(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def _resolve_audit_paths(
    base: Path,
    *,
    roots: list[Path] | None,
    filters: dict[str, Any] | None,
) -> tuple[list[Path], list[str], str]:
    """Return (abs paths, display roots, mode) for Full-tier scanning."""
    audit_globs: list[str] = []
    sync_filters = filters
    if sync_filters is None and roots is None:
        try:
            from astloom_cli.sync_config import find_sync_config_paths, resolve_sync_filters

            if find_sync_config_paths(base):
                sync_filters = resolve_sync_filters(root=base, require_config=False)
        except Exception:  # noqa: BLE001 — fall back to DEFAULT_DOC_ROOTS
            sync_filters = None

    if sync_filters and sync_filters.get("docs_enabled") and sync_filters.get("doc_match_globs"):
        audit_globs = list(sync_filters.get("doc_audit_exclude_globs") or [])
        try:
            from code_graph_service.domain.doc_discovery import discover_documentation_files

            discovered = discover_documentation_files(
                base,
                match_globs=sync_filters.get("doc_match_globs"),
                exclude_dirs=sync_filters.get("doc_exclude_dirs"),
                exclude_globs=sync_filters.get("doc_exclude_globs"),
                doc_paths=sync_filters.get("doc_paths") or None,
                max_files=int(sync_filters.get("max_files") or 20_000),
            )
        except Exception:  # noqa: BLE001
            discovered = []
        paths: list[Path] = []
        for item in discovered:
            rel = normalize_repo_rel(getattr(item, "relative_path", "") or "")
            abs_path = Path(getattr(item, "absolute_path", "") or "")
            if not rel or not abs_path.is_file():
                continue
            if not is_docs_audit_path(rel, audit_exclude_globs=audit_globs):
                continue
            paths.append(abs_path)
        display = list(sync_filters.get("sources") or []) or ["sync:docs.match"]
        return sorted(paths), display, "sync"

    scan_roots = roots or [base / name for name in DEFAULT_DOC_ROOTS]
    paths = []
    for root in scan_roots:
        root = root.resolve()
        if not root.is_dir():
            continue
        for path in _iter_markdown(root):
            try:
                rel = str(path.resolve().relative_to(base)).replace("\\", "/")
            except ValueError:
                rel = path.name
            if not is_docs_audit_path(rel, audit_exclude_globs=audit_globs):
                continue
            paths.append(path)
    return sorted(paths), [str(p.resolve()) for p in scan_roots], "roots"


def build_docs_standards_report(
    *,
    roots: list[Path] | None = None,
    repo: Path | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = (repo or repo_root()).resolve()
    paths, display_roots, mode = _resolve_audit_paths(base, roots=roots, filters=filters)
    findings: list[dict[str, Any]] = []
    for path in paths:
        try:
            findings.append(check_file(path, root=base))
        except ValueError:
            findings.append(check_file(path, root=path.parent))

    conforming = [row for row in findings if row.get("ok")]
    nonconforming = [row for row in findings if not row.get("ok")]
    nonconforming_sorted = sorted(
        nonconforming,
        key=lambda r: (-int(r.get("issue_count") or 0), str(r.get("file") or "")),
    )
    conforming_sorted = sorted(conforming, key=lambda r: str(r.get("file") or ""))

    revision_debt: list[dict[str, Any]] = []
    for row in findings:
        warns = [str(w) for w in (row.get("warnings") or [])]
        issues = [str(i) for i in (row.get("issues") or [])]
        rev_warns = [
            w
            for w in warns
            if w.startswith("missing_recommended:doc_version")
            or w.startswith("missing_recommended:updated_at")
        ]
        rev_issues = [i for i in issues if i in {"invalid_doc_version", "invalid_updated_at"}]
        if not rev_warns and not rev_issues:
            continue
        revision_debt.append(
            {
                "file": row.get("file"),
                "doc_id": row.get("doc_id"),
                "doc_version": row.get("doc_version"),
                "updated_at": row.get("updated_at"),
                "warnings": rev_warns,
                "issues": rev_issues,
                "ok": bool(row.get("ok")),
            }
        )
    revision_debt.sort(key=lambda r: str(r.get("file") or ""))

    total = len(findings)
    non_count = len(nonconforming)
    ok_count = len(conforming)
    rev_count = len(revision_debt)
    return {
        "repo": str(base),
        "roots": display_roots,
        "scan_mode": mode,
        "summary": {
            "total": total,
            "conforming_count": ok_count,
            "nonconforming_count": non_count,
            "percent_conforming": pct(ok_count, total),
            "percent_nonconforming": pct(non_count, total),
            "revision_debt_count": rev_count,
            "percent_revision_debt": pct(rev_count, total),
        },
        "nonconforming": nonconforming_sorted,
        "conforming": conforming_sorted,
        "revision_debt": revision_debt,
        "top_revision_debt": top(revision_debt, n=TOP_N),
        "top_nonconforming": top(nonconforming_sorted, n=TOP_N),
        "top_n": TOP_N,
    }
