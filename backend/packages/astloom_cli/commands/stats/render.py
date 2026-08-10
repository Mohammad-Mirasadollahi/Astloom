"""Human and file text rendering for astloom stats."""

from __future__ import annotations

from typing import Any

from astloom_cli import ui
from astloom_cli.commands.inventory.util import (
    format_pending_work_line,
    format_synced_beside_total,
)
from astloom_cli.embedding_heal_guidance import (
    format_embedding_heal_lines,
    print_embedding_heal_guidance,
)


def format_bytes(n: int) -> str:
    value = float(max(0, int(n or 0)))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{int(n)} B"


def format_language_line(row: dict[str, Any], *, detail: bool) -> str:
    lang = str(row.get("language") or "unknown")
    files = int(row.get("files") or 0)
    pct_code = row.get("percent_of_code")
    pending = format_pending_work_line(
        {
            "edited_count": row.get("edited_count") or 0,
            "remaining_count": row.get("remaining_count") or 0,
        }
    )
    base = (
        f"{lang}  {files} files ({pct_code}% of code)  "
        f"{format_bytes(int(row.get('bytes') or 0))}  ·  "
        f"{int(row.get('done_count') or 0)} already synced"
    )
    if not detail:
        return f"{base}  ·  need sync: {pending}"
    return (
        f"{base}  ·  need sync: {pending}  ·  "
        f"{row.get('percent_of_bytes')}% of code bytes"
    )


def format_summary_lines(report: dict[str, Any]) -> list[str]:
    summary = report["summary"]
    totals = report.get("totals") or {}
    code = summary["code"]
    docs = summary["docs"]
    llm = summary["llm"]
    scope = report["scope"]
    code_size = (
        f"{totals.get('code_files', code.get('total', 0))} files "
        f"({format_bytes(int(totals.get('code_bytes') or 0))})"
    )
    docs_size = (
        f"{totals.get('docs_files', docs.get('total', 0))} files "
        f"({format_bytes(int(totals.get('docs_bytes') or 0))})"
    )
    lines = [
        "Astloom stats",
        f"Scope: {scope['tenant']}/{scope['workspace']}/{scope['project']}",
        f"Paths: {len(report.get('paths') or [])}",
        f"Code:  {format_synced_beside_total(code, size_label=code_size)}",
        f"Docs:  {format_synced_beside_total(docs, size_label=docs_size)}",
        f"Need sync (code): {format_pending_work_line(code)}",
        f"Need sync (docs): {format_pending_work_line(docs)}",
        (
            f"LLM:   {llm['done_count']} of {llm['total']} symbols documented  "
            f"({llm['percent_done']}%)"
        ),
    ]
    lines.extend(format_embedding_heal_lines(summary))
    return lines


def format_detail_text(report: dict[str, Any]) -> str:
    chunks: list[str] = []
    chunks.extend(format_summary_lines(report))
    chunks.append("")
    chunks.append("By language:")
    languages = report.get("languages") or []
    if not languages:
        chunks.append("  (none)")
    else:
        for row in languages:
            chunks.append(f"  - {format_language_line(row, detail=True)}")
    chunks.append("")
    for root in report.get("results") or []:
        chunks.append(f"=== {root.get('path')} ===")
        totals = root.get("totals") or {}
        chunks.append(
            f"Totals: code={totals.get('code_files', 0)} files "
            f"({format_bytes(int(totals.get('code_bytes') or 0))})  "
            f"docs={totals.get('docs_files', 0)} files "
            f"({format_bytes(int(totals.get('docs_bytes') or 0))})"
        )
        for row in root.get("languages") or []:
            chunks.append(f"  - {format_language_line(row, detail=True)}")
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def print_human(
    report: dict[str, Any],
    *,
    detail: bool,
    title: str = "Stats",
    show_hint: bool = True,
) -> None:
    summary = report["summary"]
    totals = report.get("totals") or {}
    ui.blank()
    ui.heading(title)
    ui.blank()
    scope = report["scope"]
    ui.kv("Scope", ui.scope_line(scope["tenant"], scope["workspace"], scope["project"]))
    for path in report.get("paths") or []:
        ui.bullet(str(path))

    code = summary["code"]
    docs = summary["docs"]
    llm = summary["llm"]
    ui.blank()
    ui.section("Totals")
    ui.kv(
        "Code",
        format_synced_beside_total(
            code,
            size_label=(
                f"{totals.get('code_files', code.get('total', 0))} files "
                f"({format_bytes(int(totals.get('code_bytes') or 0))})"
            ),
        ),
    )
    ui.kv(
        "Docs",
        format_synced_beside_total(
            docs,
            size_label=(
                f"{totals.get('docs_files', docs.get('total', 0))} files "
                f"({format_bytes(int(totals.get('docs_bytes') or 0))})"
            ),
        ),
    )
    ui.kv(
        "LLM",
        (
            f"{llm['done_count']} of {llm['total']} symbols documented  "
            f"({llm['percent_done']}%)"
        ),
    )
    embeddings = summary.get("embeddings") or {}
    if embeddings:
        ui.kv(
            "Embeddings",
            (
                f"{embeddings.get('indexed_symbols', 0)} of "
                f"{embeddings.get('eligible_symbols', 0)} indexed  "
                f"({embeddings.get('coverage_percent', 100.0)}%)  "
                f"missing={embeddings.get('missing_symbols', 0)}"
            ),
        )

    ui.blank()
    ui.section("Need sync")
    ui.kv("Code", format_pending_work_line(code))
    ui.kv("Docs", format_pending_work_line(docs))
    print_embedding_heal_guidance(summary)

    ui.blank()
    ui.section("By language")
    languages = report.get("languages") or []
    if not languages:
        ui.bullet("(none)")
    else:
        for idx, row in enumerate(languages, start=1):
            ui.bullet(f"{idx}. {format_language_line(row, detail=detail)}")
    ui.blank()
    if show_hint:
        ui.bullet("Hint: astloom stats detail | save <file> | detail save <file>")
        ui.blank()


def print_sync_preflight(report: dict[str, Any], *, sync_mode: str = "") -> None:
    """Work-only preview before sync — pending code/docs/LLM/embeddings heal."""
    summary = report["summary"]
    code = summary["code"]
    docs = summary["docs"]
    llm = summary["llm"]
    ui.blank()
    ui.heading("Before sync")
    ui.blank()
    scope = report["scope"]
    ui.kv("Scope", ui.scope_line(scope["tenant"], scope["workspace"], scope["project"]))
    for path in report.get("paths") or []:
        ui.bullet(str(path))
    ui.blank()
    ui.section("Need sync")
    ui.kv("Code", format_pending_work_line(code))
    ui.kv("Docs", format_pending_work_line(docs))
    remaining_llm = int(llm.get("remaining_count") or 0)
    if remaining_llm:
        ui.kv(
            "LLM",
            f"{remaining_llm} symbols still need documentation",
        )
    print_embedding_heal_guidance(summary, sync_mode=sync_mode)
    ui.blank()
