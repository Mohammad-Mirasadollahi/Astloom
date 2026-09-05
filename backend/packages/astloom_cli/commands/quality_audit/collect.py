"""Build categorized quality-audit report (docs + code)."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from astloom_cli.commands.docs_standards.check import (
    DESIGN_TYPES,
    SOFT_BODY_LINES,
)
from astloom_cli.commands.docs_standards.collect import (
    build_docs_standards_report,
)
from astloom_cli.commands.quality_audit.categories import (
    CATEGORY_CODE_DEAD_CODE_HINT,
    CATEGORY_CODE_LOW_SYMBOL_DOCS,
    CATEGORY_CODE_MISSING_EMBEDDINGS,
    CATEGORY_CODE_NEVER_INGESTED,
    CATEGORY_CODE_STALE_EDITED,
    CATEGORY_DOCS_FLOW_TABLE,
    CATEGORY_DOCS_LANE_INVALID,
    CATEGORY_DOCS_LINKING_GAP,
    CATEGORY_DOCS_REVISION_INVALID,
    CATEGORY_DOCS_REVISION_MISSING,
    CATEGORY_DOCS_SIZE_HARD,
    CATEGORY_DOCS_SIZE_SOFT,
    CATEGORY_DOCS_STANDARDS,
    CATEGORY_DOCS_STALE_CLEANUP_HINT,
    CATEGORY_META,
    VALID_CONCERNS,
)

_REVISION_ISSUES = frozenset({"invalid_doc_version", "invalid_updated_at"})
_REVISION_WARN_PREFIXES = (
    "missing_recommended:doc_version",
    "missing_recommended:updated_at",
)
from astloom_cli.docs_link_suggest import extract_evidence_link_tokens
from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter
from astloom_cli.util import now_iso, repo_root

FLOW_TABLE_RE = re.compile(r"(?im)^\|.+\b(step|actor|action|outcome)\b.+\|")


def _finding(
    *,
    category: str,
    path: str,
    detail: str,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    meta = CATEGORY_META[category]
    return {
        "category": category,
        "severity": meta["severity"],
        "title": meta["title"],
        "path": path,
        "detail": detail,
        "evidence": list(evidence or []),
        "fix_hint": meta["fix_hint"],
    }


def _cited_path_tokens(body: str, *, root: Path) -> list[str]:
    return extract_evidence_link_tokens(body, repo=root, max_tokens=64)


def _audit_docs(root: Path, *, deadline_monotonic: float | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    standards = build_docs_standards_report(repo=root, deadline_monotonic=deadline_monotonic)
    rows = list(standards.get("nonconforming") or []) + list(standards.get("conforming") or [])
    for row in rows:
        path = str(row.get("file") or "")
        issues = [str(i) for i in (row.get("issues") or [])]
        warnings = [str(w) for w in (row.get("warnings") or [])]
        if not path:
            continue

        rev_issues = [i for i in issues if i in _REVISION_ISSUES]
        hard = [i for i in issues if i.startswith("body_over_hard_budget")]
        other = [
            i
            for i in issues
            if i not in _REVISION_ISSUES and not i.startswith("body_over_hard_budget")
        ]
        if hard:
            findings.append(
                _finding(
                    category=CATEGORY_DOCS_SIZE_HARD,
                    path=path,
                    detail="; ".join(hard),
                    evidence=hard,
                )
            )
        if rev_issues:
            findings.append(
                _finding(
                    category=CATEGORY_DOCS_REVISION_INVALID,
                    path=path,
                    detail="; ".join(rev_issues),
                    evidence=rev_issues,
                )
            )
        if other:
            findings.append(
                _finding(
                    category=CATEGORY_DOCS_STANDARDS,
                    path=path,
                    detail="; ".join(other),
                    evidence=other,
                )
            )
        rev_warns = [
            w
            for w in warnings
            if any(w.startswith(p) for p in _REVISION_WARN_PREFIXES)
        ]
        if rev_warns:
            findings.append(
                _finding(
                    category=CATEGORY_DOCS_REVISION_MISSING,
                    path=path,
                    detail="; ".join(rev_warns),
                    evidence=rev_warns,
                )
            )
        soft = [w for w in warnings if str(w).startswith("body_over_soft_budget")]
        if soft:
            findings.append(
                _finding(
                    category=CATEGORY_DOCS_SIZE_SOFT,
                    path=path,
                    detail="; ".join(soft),
                    evidence=soft,
                )
            )

    for row in rows:
        rel = str(row.get("file") or "")
        if not rel:
            continue
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = parse_markdown_frontmatter(text)
        concern = str((fm or {}).get("concern_lane") or "").strip()
        if concern and concern not in VALID_CONCERNS:
            findings.append(
                _finding(
                    category=CATEGORY_DOCS_LANE_INVALID,
                    path=rel,
                    detail=f"concern_lane={concern!r} not in closed set",
                    evidence=[concern],
                )
            )
        existing = {
            str(x).strip()
            for x in ((fm or {}).get("linked_symbols") or [])
            if isinstance((fm or {}).get("linked_symbols"), list) and str(x).strip()
        }
        cited = _cited_path_tokens(body, root=root)
        missing = [t for t in cited if t not in existing]
        if cited and (not existing or missing):
            findings.append(
                _finding(
                    category=CATEGORY_DOCS_LINKING_GAP,
                    path=rel,
                    detail=(
                        "missing linked_symbols"
                        if not existing
                        else f"missing_linked_symbols:{len(missing)}"
                    ),
                    evidence=missing[:12] or cited[:12],
                )
            )
        doc_type = str((fm or {}).get("doc_type") or "").strip()
        if doc_type in DESIGN_TYPES:
            if "```mermaid" not in body.lower():
                continue
            if not FLOW_TABLE_RE.search(body):
                findings.append(
                    _finding(
                        category=CATEGORY_DOCS_FLOW_TABLE,
                        path=rel,
                        detail="design doc has Mermaid but no agent-readable flow table",
                        evidence=["mermaid_without_flow_table"],
                    )
                )
    linking_gaps = [f for f in findings if f.get("category") == CATEGORY_DOCS_LINKING_GAP]
    if linking_gaps:
        sample = str(linking_gaps[0].get("path") or "")
        findings.append(
            _finding(
                category=CATEGORY_DOCS_STALE_CLEANUP_HINT,
                path=sample,
                detail=(
                    f"linking_gaps={len(linking_gaps)}; "
                    "call astloom_docs_stale_candidates after sync "
                    "(prefer safe_to_update/safe_to_unlink; safe_to_delete only score>=0.8)"
                ),
                evidence=[
                    "maps_to:docs.stale_candidates",
                    "skill:astloom-remove-stale-docs",
                    f"linking_gap_count={len(linking_gaps)}",
                ],
            )
        )
    return findings


def _audit_code(
    args: Any | None,
    roots: list[Path] | None = None,
    *,
    deadline_monotonic: float | None = None,
    scope: Any | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Best-effort code inventory findings; empty if roots/filters unavailable."""
    import time

    meta: dict[str, Any] = {"available": False, "error": "", "truncated": False}
    findings: list[dict[str, Any]] = []
    if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
        meta["error"] = "budget_exhausted_before_code_audit"
        meta["truncated"] = True
        return findings, meta
    try:
        import argparse

        from astloom_cli.commands.inventory.collect import build_inventory_report
    except Exception as exc:  # noqa: BLE001
        meta["error"] = f"imports failed: {exc}"
        return findings, meta

    try:
        ns = args if args is not None else argparse.Namespace()
        if roots is None:
            report = build_inventory_report(
                ns, deadline_monotonic=deadline_monotonic, scope=scope
            )
        else:
            report = build_inventory_report(
                ns, roots=roots, deadline_monotonic=deadline_monotonic, scope=scope
            )
    except (Exception, SystemExit) as exc:  # noqa: BLE001 — inventory/sync-config
        meta["error"] = str(exc)
        return findings, meta

    if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
        meta["truncated"] = True

    meta["available"] = True
    meta["paths"] = list(report.get("paths") or [])
    meta["summary"] = report.get("summary") or {}

    remaining_paths: list[str] = []
    edited_paths: list[str] = []
    low_doc_paths: list[tuple[str, str]] = []
    missing_embedding_paths: list[tuple[str, str]] = []
    for root_row in report.get("results") or []:
        if not isinstance(root_row, dict):
            continue
        code = root_row.get("code") or {}
        for item in code.get("remaining_files") or []:
            path = _item_path(item)
            if path:
                remaining_paths.append(path)
        for item in code.get("edited_files") or []:
            path = _item_path(item)
            if path:
                edited_paths.append(path)
        for item in code.get("done_files") or []:
            if not isinstance(item, dict):
                continue
            path = _item_path(item)
            sym_total = int(item.get("symbols") or 0)
            sym_docs = int(item.get("documented") or 0)
            if path and sym_total >= 5 and sym_docs * 2 < sym_total:
                low_doc_paths.append(
                    (path, f"documented {sym_docs}/{sym_total} symbols")
                )
            embedding_missing = int(item.get("embedding_missing") or 0)
            if path and embedding_missing:
                missing_embedding_paths.append(
                    (
                        path,
                        f"{embedding_missing}/{int(item.get('embedding_eligible') or 0)} "
                        "searchable symbols lack embedding rows",
                    )
                )

    for path in remaining_paths[:200]:
        findings.append(
            _finding(
                category=CATEGORY_CODE_NEVER_INGESTED,
                path=path,
                detail="not ingested into code graph",
            )
        )
    for path in edited_paths[:200]:
        findings.append(
            _finding(
                category=CATEGORY_CODE_STALE_EDITED,
                path=path,
                detail="content changed since last ingest",
            )
        )
    for path, detail in low_doc_paths[:100]:
        findings.append(
            _finding(
                category=CATEGORY_CODE_LOW_SYMBOL_DOCS,
                path=path,
                detail=detail,
            )
        )
    for path, detail in missing_embedding_paths[:200]:
        findings.append(
            _finding(
                category=CATEGORY_CODE_MISSING_EMBEDDINGS,
                path=path,
                detail=detail,
            )
        )
    # Deep-link: after stale/never-ingested inventory, point agents at scored unused-candidates.
    if remaining_paths or edited_paths:
        sample = (edited_paths or remaining_paths)[0]
        findings.append(
            _finding(
                category=CATEGORY_CODE_DEAD_CODE_HINT,
                path=sample,
                detail=(
                    f"inventory hints cleanup: stale={len(edited_paths)} "
                    f"never_ingested={len(remaining_paths)}; "
                    "call astloom_code_graph_unused_candidates after sync "
                    "(prefer path_prefix; act only safe_to_delete score>=0.8 same change)"
                ),
                evidence=[
                    "maps_to:code_graph.unused_candidates",
                    "skill:astloom-remove-dead-code",
                    "act:safe_to_delete_score_ge_0.8",
                    f"stale_count={len(edited_paths)}",
                    f"never_ingested_count={len(remaining_paths)}",
                ],
            )
        )
    return findings, meta


def _item_path(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(
            item.get("path")
            or item.get("file")
            or item.get("relative_path")
            or ""
        ).strip()
    return ""


def build_quality_audit_report(
    args: Any | None = None,
    *,
    repos: list[Path] | None = None,
    deadline_monotonic: float | None = None,
    scope: Any | None = None,
) -> dict[str, Any]:
    import time

    if repos:
        roots = [Path(p).expanduser().resolve() for p in repos]
    else:
        roots = [repo_root().resolve()]
    if not roots:
        roots = [repo_root().resolve()]
    truncated_phases: list[str] = []
    # Code first: inventory is project-scoped graph truth and was previously starved
    # when docs consumed the entire MCP soft budget on sshfs trees.
    if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
        code_findings: list[dict[str, Any]] = []
        code_meta: dict[str, Any] = {
            "available": False,
            "error": "budget_exhausted_before_code_audit",
            "truncated": True,
        }
        truncated_phases.append("code")
    else:
        code_findings, code_meta = _audit_code(
            args,
            roots=roots,
            deadline_monotonic=deadline_monotonic,
            scope=scope,
        )
        if code_meta.get("truncated"):
            truncated_phases.append("code")

    docs_findings: list[dict[str, Any]] = []
    for root in roots:
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            truncated_phases.append("docs")
            break
        docs_findings.extend(_audit_docs(root, deadline_monotonic=deadline_monotonic))
    findings = docs_findings + code_findings
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in findings:
        by_category[str(row["category"])].append(row)

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    findings_sorted = sorted(
        findings,
        key=lambda r: (
            severity_rank.get(str(r.get("severity")), 9),
            str(r.get("category")),
            str(r.get("path")),
        ),
    )
    category_summary = []
    for cat_id, meta in CATEGORY_META.items():
        rows = by_category.get(cat_id) or []
        category_summary.append(
            {
                "category": cat_id,
                "title": meta["title"],
                "severity": meta["severity"],
                "meaning": meta["meaning"],
                "fix_hint": meta["fix_hint"],
                "count": len(rows),
            }
        )
    category_summary.sort(key=lambda r: (-int(r["count"]), severity_rank.get(r["severity"], 9)))

    degraded = bool(truncated_phases)
    return {
        "ok": True,
        "degraded": degraded,
        "truncated_phases": truncated_phases,
        "generated_at": now_iso(),
        "repo": str(roots[0]) if len(roots) == 1 else str(roots[0]),
        "repos": [str(r) for r in roots],
        "summary": {
            "findings_total": len(findings),
            "docs_findings": len(docs_findings),
            "code_findings": len(code_findings),
            "categories_with_findings": sum(1 for c in category_summary if int(c["count"]) > 0),
            "soft_budget_lines": SOFT_BODY_LINES,
            "degraded": degraded,
            "truncated_phases": truncated_phases,
        },
        "code_audit": code_meta,
        "categories": category_summary,
        "findings": findings_sorted,
        "by_category": {k: v for k, v in sorted(by_category.items())},
    }
