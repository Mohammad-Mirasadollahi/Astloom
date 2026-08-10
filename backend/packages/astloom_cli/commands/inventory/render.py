"""Human and file text rendering for inventory."""

from __future__ import annotations

from typing import Any

from astloom_cli import ui
from astloom_cli.commands.inventory.util import (
    TOP_N,
    format_pending_work_line,
    sort_done,
    sort_remaining,
    top,
)
from astloom_cli.embedding_heal_guidance import (
    format_embedding_heal_lines,
    print_embedding_heal_guidance,
)


def format_file_line(row: dict[str, Any], *, detail: bool) -> str:
    path = str(row.get("file") or "")
    models = row.get("models") or []
    model_txt = ",".join(models) if models else "-"
    status = str(row.get("status") or "")
    reason = str(row.get("edit_reason") or "")
    status_bit = f"  status={status}" if status else ""
    reason_bit = f"  reason={reason}" if reason else ""
    if not detail:
        return f"{path}  models={model_txt}{status_bit}{reason_bit}"
    return (
        f"{path}  models={model_txt}{status_bit}{reason_bit}  "
        f"embed={','.join(row.get('embed_models') or []) or '-'}  "
        f"docs={','.join(row.get('docs_models') or []) or '-'}  "
        f"symbols={row.get('documented', 0)}/{row.get('symbols', 0)}  "
        f"({row.get('doc_percent', 0)}%)"
    )


def format_summary_lines(report: dict[str, Any]) -> list[str]:
    summary = report["summary"]
    code = summary["code"]
    docs = summary["docs"]
    llm = summary["llm"]
    scope = report["scope"]
    processing = report.get("processing") or {}
    lines = [
        "Astloom inventory",
        f"Scope: {scope['tenant']}/{scope['workspace']}/{scope['project']}",
        f"Paths: {len(report.get('paths') or [])}",
        (
            f"Code:  {code['done_count']} of {code['total']} already synced  "
            f"({code['percent_done']}%)  ·  need sync: {format_pending_work_line(code)}"
        ),
        (
            f"Docs:  {docs['done_count']} of {docs['total']} already synced  "
            f"({docs['percent_done']}%)  ·  need sync: {format_pending_work_line(docs)}"
        ),
        (
            f"LLM:   {llm['done_count']} of {llm['total']} symbols documented  "
            f"({llm['percent_done']}%)"
        ),
        f"Docs model: {processing.get('docs_model_label') or '-'}",
        f"Embed model: {processing.get('active_embed_model') or '-'}",
        (
            f"Embeddings: {summary.get('embeddings', {}).get('indexed_symbols', 0)} of "
            f"{summary.get('embeddings', {}).get('eligible_symbols', 0)} indexed "
            f"({summary.get('embeddings', {}).get('coverage_percent', 100.0)}%); "
            f"missing={summary.get('embeddings', {}).get('missing_symbols', 0)}"
        ),
        f"Models used: {', '.join(report.get('models_used') or []) or '-'}",
    ]
    if int(code.get("edited_count") or 0) or int(docs.get("edited_count") or 0):
        lines.append("Hint: edited files were ingested before but changed — run astloom sync")
    lines.extend(format_embedding_heal_lines(summary))
    return lines


def _section_files(
    chunks: list[str],
    *,
    title: str,
    percent: Any,
    rows: list[dict[str, Any]] | None,
    mark: str,
) -> None:
    if percent is None:
        chunks.append(f"{title} — showing {len(rows or [])}:")
    else:
        chunks.append(f"{title} ({percent}%) — showing {len(rows or [])}:")
    chunks.extend(f"  {mark} {format_file_line(item, detail=True)}" for item in (rows or []))
    if not rows:
        chunks.append("  (none)")


def format_detail_text(report: dict[str, Any], *, top_only: bool = False) -> str:
    """Plain-text details suitable for save files."""
    chunks: list[str] = []
    chunks.extend(format_summary_lines(report))
    chunks.append("")
    for row in report.get("results") or []:
        chunks.append(f"=== {row['path']} ===")
        code = row["code"]
        docs = row["docs"]
        done_code = code.get("top_done") if top_only else code.get("done_files")
        edited_code = code.get("top_edited") if top_only else code.get("edited_files")
        rem_code = code.get("top_remaining") if top_only else code.get("remaining_files")
        done_docs = docs.get("top_done") if top_only else docs.get("done_files")
        edited_docs = docs.get("top_edited") if top_only else docs.get("edited_files")
        rem_docs = docs.get("top_remaining") if top_only else docs.get("remaining_files")
        _section_files(
            chunks,
            title="Code done",
            percent=code.get("percent_done"),
            rows=done_code,
            mark="+",
        )
        _section_files(
            chunks,
            title="Code edited",
            percent=None,
            rows=edited_code,
            mark="~",
        )
        _section_files(
            chunks,
            title="Code remaining",
            percent=code.get("percent_remaining"),
            rows=rem_code,
            mark="-",
        )
        _section_files(
            chunks,
            title="Docs done",
            percent=docs.get("percent_done"),
            rows=done_docs,
            mark="+",
        )
        _section_files(
            chunks,
            title="Docs edited",
            percent=None,
            rows=edited_docs,
            mark="~",
        )
        _section_files(
            chunks,
            title="Docs remaining",
            percent=docs.get("percent_remaining"),
            rows=rem_docs,
            mark="-",
        )
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def print_file_top(
    title: str,
    rows: list[dict[str, Any]],
    *,
    detail: bool,
    percent: float | None = None,
) -> None:
    label = title if percent is None else f"{title} ({percent}%)"
    ui.section(label)
    if not rows:
        ui.bullet("(none)")
        return
    for idx, row in enumerate(rows, start=1):
        ui.bullet(f"{idx}. {format_file_line(row, detail=detail)}")


# Back-compat alias for tests.
_edited_percent_line = format_pending_work_line


def print_human(report: dict[str, Any], *, detail: bool) -> None:
    summary = report["summary"]
    processing = report.get("processing") or {}
    ui.blank()
    ui.heading("Inventory")
    ui.blank()
    scope = report["scope"]
    ui.kv("Scope", ui.scope_line(scope["tenant"], scope["workspace"], scope["project"]))
    paths = report.get("paths") or []
    ui.kv("Paths", f"{len(paths)} root(s)")
    for path in paths:
        ui.bullet(str(path))

    ui.blank()
    ui.section("Totals")
    code = summary["code"]
    docs = summary["docs"]
    llm = summary["llm"]
    ui.kv(
        "Code",
        f"{code['done_count']} of {code['total']} already synced  ({code['percent_done']}%)",
    )
    ui.kv(
        "Docs",
        f"{docs['done_count']} of {docs['total']} already synced  ({docs['percent_done']}%)",
    )
    ui.kv(
        "LLM",
        (
            f"{llm['done_count']} of {llm['total']} symbols documented  "
            f"({llm['percent_done']}%)"
        ),
    )
    embeddings = summary.get("embeddings") or {}
    ui.kv(
        "Embeddings",
        (
            f"{embeddings.get('indexed_symbols', 0)} of "
            f"{embeddings.get('eligible_symbols', 0)} indexed  "
            f"({embeddings.get('coverage_percent', 100.0)}%)  "
            f"missing={embeddings.get('missing_symbols', 0)}"
        ),
    )
    print_embedding_heal_guidance(summary)

    ui.blank()
    ui.section("Need sync")
    ui.kv("Code", format_pending_work_line(code))
    ui.kv("Docs", format_pending_work_line(docs))

    ui.blank()
    ui.section("Models")
    ui.kv("Docs model", str(processing.get("docs_model_label") or "-"))
    ui.kv("Embed model", str(processing.get("active_embed_model") or "-"))
    used = report.get("models_used") or []
    ui.kv("Seen", ", ".join(used) if used else "-")

    code_done: list[dict[str, Any]] = []
    code_edited: list[dict[str, Any]] = []
    code_rem: list[dict[str, Any]] = []
    docs_done: list[dict[str, Any]] = []
    docs_edited: list[dict[str, Any]] = []
    docs_rem: list[dict[str, Any]] = []
    for row in report.get("results") or []:
        code_done.extend(row["code"].get("done_files") or [])
        code_edited.extend(row["code"].get("edited_files") or [])
        code_rem.extend(row["code"].get("remaining_files") or [])
        docs_done.extend(row["docs"].get("done_files") or [])
        docs_edited.extend(row["docs"].get("edited_files") or [])
        docs_rem.extend(row["docs"].get("remaining_files") or [])
    code_done = top(sort_done(code_done))
    code_edited = top(sort_done(code_edited))
    code_rem = top(sort_remaining(code_rem))
    docs_done = top(sort_done(docs_done))
    docs_edited = top(sort_done(docs_edited))
    docs_rem = top(sort_remaining(docs_rem))

    ui.blank()
    print_file_top(
        f"Top {TOP_N} code done",
        code_done,
        detail=detail,
        percent=float(code["percent_done"]),
    )
    print_file_top(
        f"Top {TOP_N} code edited",
        code_edited,
        detail=detail,
        percent=None,
    )
    print_file_top(
        f"Top {TOP_N} code remaining",
        code_rem,
        detail=detail,
        percent=float(code.get("percent_remaining") or 0),
    )
    print_file_top(
        f"Top {TOP_N} docs done",
        docs_done,
        detail=detail,
        percent=float(docs["percent_done"]),
    )
    print_file_top(
        f"Top {TOP_N} docs edited",
        docs_edited,
        detail=detail,
        percent=None,
    )
    print_file_top(
        f"Top {TOP_N} docs remaining",
        docs_rem,
        detail=detail,
        percent=float(docs.get("percent_remaining") or 0),
    )
    ui.blank()
