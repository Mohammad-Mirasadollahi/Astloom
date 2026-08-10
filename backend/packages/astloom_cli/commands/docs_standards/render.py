"""Human and file text rendering for docs-standards."""

from __future__ import annotations

from typing import Any

from astloom_cli import ui


def format_finding_line(row: dict[str, Any], *, detail: bool) -> str:
    path = str(row.get("file") or "")
    count = int(row.get("issue_count") or 0)
    warns = int(row.get("warning_count") or 0)
    warn_bit = f"  warnings={warns}" if warns else ""
    if not detail:
        return f"{path}  issues={count}{warn_bit}"
    issues = ", ".join(row.get("issues") or []) or "-"
    warnings = ", ".join(row.get("warnings") or [])
    warn_detail = f"  warnings=[{warnings}]" if warnings else ""
    doc_id = row.get("doc_id") or "-"
    doc_type = row.get("doc_type") or "-"
    return (
        f"{path}  issues={count}  doc_id={doc_id}  doc_type={doc_type}  "
        f"[{issues}]{warn_detail}"
    )


def format_summary_lines(report: dict[str, Any]) -> list[str]:
    summary = report["summary"]
    return [
        "Astloom docs-standards",
        f"Repo: {report.get('repo')}",
        f"Roots: {len(report.get('roots') or [])}",
        (
            f"Conforming: {summary['conforming_count']}/{summary['total']} "
            f"({summary['percent_conforming']}%)"
        ),
        (
            f"Nonconforming: {summary['nonconforming_count']}/{summary['total']} "
            f"({summary['percent_nonconforming']}%)"
        ),
        (
            f"Revision debt: {summary.get('revision_debt_count', 0)}/{summary['total']} "
            f"({summary.get('percent_revision_debt', 0)}%)  "
            "(missing/invalid doc_version or updated_at)"
        ),
    ]


def format_detail_text(report: dict[str, Any], *, top_only: bool = False) -> str:
    chunks: list[str] = []
    chunks.extend(format_summary_lines(report))
    chunks.append("")
    rows = report.get("top_nonconforming") if top_only else report.get("nonconforming")
    chunks.append(
        f"Nonconforming ({report['summary']['percent_nonconforming']}%) — "
        f"showing {len(rows or [])}:"
    )
    if rows:
        for row in rows:
            chunks.append(f"  - {format_finding_line(row, detail=True)}")
    else:
        chunks.append("  (none)")
    chunks.append("")

    rev_rows = report.get("top_revision_debt") if top_only else report.get("revision_debt")
    chunks.append(
        f"Revision debt ({report['summary'].get('percent_revision_debt', 0)}%) — "
        f"showing {len(rev_rows or [])}:"
    )
    if rev_rows:
        for row in rev_rows:
            path = row.get("file") or ""
            bits = list(row.get("issues") or []) + list(row.get("warnings") or [])
            chunks.append(
                f"  - {path}  doc_version={row.get('doc_version') or '-'}  "
                f"updated_at={row.get('updated_at') or '-'}  [{', '.join(bits) or '-'}]"
            )
    else:
        chunks.append("  (none)")
    chunks.append("")
    chunks.append(
        "Hint: python scripts/stamp_docs_revision.py --date YYYY-MM-DD  "
        "(baseline) or bump doc_version + updated_at on material edits."
    )
    chunks.append("")

    if not top_only:
        ok_rows = report.get("conforming") or []
        chunks.append(
            f"Conforming ({report['summary']['percent_conforming']}%) — "
            f"showing {len(ok_rows)}:"
        )
        for row in ok_rows:
            chunks.append(f"  + {row.get('file')}")
        if not ok_rows:
            chunks.append("  (none)")
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def print_human(report: dict[str, Any], *, detail: bool) -> None:
    summary = report["summary"]
    ui.blank()
    ui.heading("Docs standards")
    ui.blank()
    ui.kv("Repo", str(report.get("repo") or "-"))
    for root in report.get("roots") or []:
        ui.bullet(str(root))

    ui.blank()
    ui.section("Percent")
    ui.kv(
        "Conforming",
        f"{summary['conforming_count']}/{summary['total']}  ({summary['percent_conforming']}%)",
    )
    ui.kv(
        "Nonconforming",
        f"{summary['nonconforming_count']}/{summary['total']}  ({summary['percent_nonconforming']}%)",
    )
    ui.kv(
        "Revision debt",
        f"{summary.get('revision_debt_count', 0)}/{summary['total']}  "
        f"({summary.get('percent_revision_debt', 0)}%)",
    )

    top_n = int(report.get("top_n") or 10)
    ui.blank()
    ui.section(f"Top {top_n} nonconforming ({summary['percent_nonconforming']}%)")
    rows = report.get("top_nonconforming") or []
    if not rows:
        ui.bullet("(none)")
    else:
        for idx, row in enumerate(rows, start=1):
            ui.bullet(f"{idx}. {format_finding_line(row, detail=detail)}")

    ui.blank()
    ui.section(f"Top {top_n} revision debt ({summary.get('percent_revision_debt', 0)}%)")
    rev_rows = report.get("top_revision_debt") or []
    if not rev_rows:
        ui.bullet("(none)")
    else:
        for idx, row in enumerate(rev_rows, start=1):
            bits = list(row.get("issues") or []) + list(row.get("warnings") or [])
            ui.bullet(
                f"{idx}. {row.get('file')}  "
                f"doc_version={row.get('doc_version') or '-'}  "
                f"updated_at={row.get('updated_at') or '-'}  "
                f"[{', '.join(bits) or '-'}]"
            )

    ui.blank()
    ui.bullet(
        "Hint: astloom docs-standards detail | save <file> | "
        "python scripts/stamp_docs_revision.py --date YYYY-MM-DD"
    )
    ui.blank()
