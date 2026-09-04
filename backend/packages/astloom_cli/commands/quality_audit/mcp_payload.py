"""Compact quality-audit payloads for MCP coding agents."""

from __future__ import annotations

from typing import Any


def compact_quality_audit_payload(
    report: dict[str, Any],
    *,
    top_n: int = 25,
    severities: list[str] | None = None,
) -> dict[str, Any]:
    """Shrink a full report to summary + actionable top findings."""
    allowed = {s.lower() for s in (severities or []) if s}
    findings = list(report.get("findings") or [])
    if allowed:
        findings = [f for f in findings if str(f.get("severity") or "").lower() in allowed]

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    findings_sorted = sorted(
        findings,
        key=lambda r: (
            severity_rank.get(str(r.get("severity")), 9),
            str(r.get("category")),
            str(r.get("path")),
        ),
    )
    top = findings_sorted[:top_n]
    actionable = [
        f
        for f in findings_sorted
        if str(f.get("severity") or "").lower() in {"high", "medium"}
    ]
    return {
        "repo": report.get("repo"),
        "repos": report.get("repos") or ([report.get("repo")] if report.get("repo") else []),
        "generated_at": report.get("generated_at"),
        "summary": report.get("summary") or {},
        "categories": report.get("categories") or [],
        "findings_total": len(findings_sorted),
        "actionable_count": len(actionable),
        "must_remediate": len(actionable) > 0,
        "agent_instruction": (
            "Load skill astloom-quality-audit and remediate high/medium findings "
            "(or create durable tasks) before treating the session work as done."
            if actionable
            else "No high/medium quality findings."
        ),
        "findings": [
            {
                "category": f.get("category"),
                "severity": f.get("severity"),
                "title": f.get("title"),
                "path": f.get("path"),
                "detail": f.get("detail"),
                "evidence": list(f.get("evidence") or [])[:12],
                "fix_hint": f.get("fix_hint"),
            }
            for f in top
        ],
        "top_n": top_n,
    }
