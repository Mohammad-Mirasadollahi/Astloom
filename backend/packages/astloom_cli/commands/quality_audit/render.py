"""Human + file rendering for quality-audit."""

from __future__ import annotations

from typing import Any

from astloom_cli import ui
from astloom_cli.commands.inventory.util import TOP_N


def format_detail_text(report: dict[str, Any], *, top_only: bool = True) -> str:
    summary = report.get("summary") or {}
    lines = [
        "Astloom quality-audit",
        f"Repo: {report.get('repo')}",
        f"Generated: {report.get('generated_at')}",
        (
            f"Findings: {summary.get('findings_total')}  "
            f"(docs={summary.get('docs_findings')}  code={summary.get('code_findings')})  "
            f"categories_hit={summary.get('categories_with_findings')}"
        ),
        "",
        "Categories:",
    ]
    for cat in report.get("categories") or []:
        if int(cat.get("count") or 0) <= 0 and top_only:
            continue
        lines.append(
            f"  - [{cat.get('severity')}] {cat.get('category')}  "
            f"count={cat.get('count')}  — {cat.get('title')}"
        )
        lines.append(f"      meaning: {cat.get('meaning')}")
        lines.append(f"      fix: {cat.get('fix_hint')}")

    code_meta = report.get("code_audit") or {}
    if not code_meta.get("available"):
        lines.append("")
        lines.append(f"Code audit unavailable: {code_meta.get('error') or 'n/a'}")

    lines.append("")
    findings = list(report.get("findings") or [])
    shown = findings[:TOP_N] if top_only else findings
    label = f"Findings (top {len(shown)}/{len(findings)})" if top_only else f"Findings ({len(findings)})"
    lines.append(f"{label}:")
    if not shown:
        lines.append("  (none)")
    for row in shown:
        lines.append(
            f"  - [{row.get('severity')}] {row.get('category')}  {row.get('path')}"
        )
        lines.append(f"      {row.get('detail')}")
        evidence = list(row.get("evidence") or [])
        if evidence:
            lines.append(f"      evidence: {', '.join(str(x) for x in evidence[:8])}")
    lines.append("")
    return "\n".join(lines)


def print_human(report: dict[str, Any], *, detail: bool) -> None:
    summary = report.get("summary") or {}
    ui.blank()
    ui.heading("Quality audit")
    ui.kv("Repo", str(report.get("repo")))
    ui.kv("Generated", str(report.get("generated_at")))
    ui.kv(
        "Findings",
        f"total={summary.get('findings_total')}  "
        f"docs={summary.get('docs_findings')}  "
        f"code={summary.get('code_findings')}",
    )
    ui.blank()
    ui.section("Categories")
    for cat in report.get("categories") or []:
        count = int(cat.get("count") or 0)
        if count <= 0 and not detail:
            continue
        ui.bullet(
            f"[{cat.get('severity')}] {cat.get('category')}  count={count}  — {cat.get('title')}"
        )
        if detail or count > 0:
            ui.kv("  meaning", str(cat.get("meaning")))
            ui.kv("  fix", str(cat.get("fix_hint")))

    code_meta = report.get("code_audit") or {}
    if not code_meta.get("available"):
        ui.blank()
        ui.kv("Code audit", f"skipped ({code_meta.get('error') or 'unavailable'})")

    findings = list(report.get("findings") or [])
    ui.blank()
    ui.section("Findings" + ("" if detail else f" (top {min(TOP_N, len(findings))})"))
    shown = findings if detail else findings[:TOP_N]
    if not shown:
        ui.bullet("(none)")
    for row in shown:
        ui.bullet(f"[{row.get('severity')}] {row.get('category')}  {row.get('path')}")
        ui.kv("  detail", str(row.get("detail")))
        evidence = list(row.get("evidence") or [])
        if evidence and detail:
            ui.kv("  evidence", ", ".join(str(x) for x in evidence[:8]))
    ui.blank()
    ui.bullet("Hint: astloom quality-audit detail | save | detail save [<file>]")
    ui.blank()
