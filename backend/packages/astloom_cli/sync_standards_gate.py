"""Pre-sync interactive gate: optionally skip Full-tier-nonconforming docs.

Module contract:
- Role: decide whether Phase-2 human-doc ingest should exclude paths that fail
  Full-tier ``docs-standards`` for this sync run.
- Source of truth: ``check_file`` on Phase-2-discovered paths that pass docs
  audit eligibility (``is_docs_audit_path`` + ``docs.audit.exclude`` from sync
  YAML). Package README / AGENTS basenames are never gated.
- Failures: non-TTY without ``--skip-nonconforming`` does not skip (CI-safe).
  Missing discovery/check never blocks sync — returns empty skip set.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from astloom_cli import ui
from astloom_cli.docs_audit_scope import (
    is_docs_audit_path,
    normalize_repo_rel,
)

ReadFn = Callable[[str], str]


@dataclass
class StandardsGateResult:
    """Outcome of the pre-sync standards gate for one sync root."""

    mode: str = "include"  # ask | skip | include
    skipped: bool = False
    docs_nonconforming: list[str] = field(default_factory=list)
    code_nonconforming: list[str] = field(default_factory=list)
    skipped_docs: list[str] = field(default_factory=list)
    skipped_code: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "skipped": self.skipped,
            "docs_nonconforming": list(self.docs_nonconforming),
            "code_nonconforming": list(self.code_nonconforming),
            "skipped_docs": list(self.skipped_docs),
            "skipped_code": list(self.skipped_code),
        }


def path_to_exclude_glob(relative_path: str) -> str:
    """Exact relative path as an exclude glob (fnmatch-friendly)."""
    return normalize_repo_rel(relative_path)


def list_nonconforming_docs(
    *,
    root_path: Path,
    filters: dict[str, Any],
) -> list[str]:
    """Return audit-eligible Phase-2 docs that fail docs-standards.

    Eligibility: discovered via ``docs.match`` / ``docs.exclude``, then
    ``is_docs_audit_path`` (README/AGENTS hard-skip + ``docs.audit.exclude``).
    """
    if not filters.get("docs_enabled", True):
        return []
    match_globs = list(filters.get("doc_match_globs") or [])
    if not match_globs:
        return []

    try:
        from code_graph_service.domain.doc_discovery import discover_documentation_files
        from astloom_cli.commands.docs_standards.check import check_file
    except Exception:  # noqa: BLE001 — gate must not block sync
        return []

    root_path = root_path.expanduser().resolve()
    try:
        discovered = discover_documentation_files(
            root_path,
            match_globs=match_globs,
            exclude_dirs=filters.get("doc_exclude_dirs"),
            exclude_globs=filters.get("doc_exclude_globs"),
            doc_paths=filters.get("doc_paths") or None,
            max_files=int(filters.get("max_files") or 2000),
        )
    except Exception:  # noqa: BLE001
        return []

    audit_globs = list(filters.get("doc_audit_exclude_globs") or [])
    bad: list[str] = []
    for item in discovered:
        rel = normalize_repo_rel(getattr(item, "relative_path", "") or "")
        abs_path = Path(getattr(item, "absolute_path", "") or "")
        if not rel or not abs_path.is_file():
            continue
        if not is_docs_audit_path(rel, audit_exclude_globs=audit_globs):
            continue
        try:
            row = check_file(abs_path, root=root_path)
        except Exception:  # noqa: BLE001
            continue
        if not row.get("ok"):
            bad.append(rel)
    return sorted(set(bad))


def apply_nonconforming_excludes(
    filters: dict[str, Any],
    *,
    docs: list[str] | None = None,
    code: list[str] | None = None,
) -> dict[str, Any]:
    """Return a shallow-copied filter dict with per-path excludes added."""
    out = dict(filters)
    doc_globs = list(out.get("doc_exclude_globs") or [])
    code_globs = list(out.get("exclude_globs") or [])
    for rel in docs or []:
        glob = path_to_exclude_glob(rel)
        if glob and glob not in doc_globs:
            doc_globs.append(glob)
    for rel in code or []:
        glob = path_to_exclude_glob(rel)
        if glob and glob not in code_globs:
            code_globs.append(glob)
    out["doc_exclude_globs"] = doc_globs
    out["exclude_globs"] = code_globs
    return out


def _read_yes_no(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError as exc:
        raise SystemExit(
            "error: standards gate aborted (no input). Nothing was synced."
        ) from exc


def resolve_standards_gate(
    *,
    root_path: Path,
    filters: dict[str, Any],
    skip_nonconforming: bool = False,
    sync_nonconforming: bool = False,
    input_fn: ReadFn | None = None,
    stdin_isatty: bool | None = None,
    code_nonconforming: list[str] | None = None,
) -> tuple[dict[str, Any], StandardsGateResult]:
    """Apply interactive/flagged skip of nonconforming paths; return filters + result.

    ``code_nonconforming`` is reserved for a future machine code-standards gate;
    today the CLI only auto-detects Full-tier docs failures.
    """
    if skip_nonconforming and sync_nonconforming:
        raise SystemExit(
            "error: use only one of --skip-nonconforming or --sync-nonconforming"
        )

    docs = list_nonconforming_docs(root_path=root_path, filters=filters)
    code = [
        normalize_repo_rel(p)
        for p in (code_nonconforming or [])
        if normalize_repo_rel(p)
    ]
    result = StandardsGateResult(
        docs_nonconforming=docs,
        code_nonconforming=code,
    )

    if not docs and not code:
        result.mode = "include"
        return filters, result

    if sync_nonconforming:
        result.mode = "include"
        return filters, result

    if skip_nonconforming:
        result.mode = "skip"
        result.skipped = True
        result.skipped_docs = list(docs)
        result.skipped_code = list(code)
        return apply_nonconforming_excludes(filters, docs=docs, code=code), result

    tty = sys.stdin.isatty() if stdin_isatty is None else bool(stdin_isatty)
    if not tty:
        # Scripts/CI: do not change sync set unless explicitly flagged.
        result.mode = "include"
        return filters, result

    result.mode = "ask"
    ui.blank()
    ui.heading("Standards gate")
    ui.blank()
    if docs:
        ui.kv("Nonconforming docs", str(len(docs)))
        sample = ", ".join(docs[:6])
        if len(docs) > 6:
            sample += f", … (+{len(docs) - 6})"
        ui.kv("Sample", sample)
    if code:
        ui.kv("Nonconforming code", str(len(code)))
        sample = ", ".join(code[:6])
        if len(code) > 6:
            sample += f", … (+{len(code) - 6})"
        ui.kv("Sample code", sample)
    ui.blank()
    ui.bullet(
        "Skipping keeps nonconforming paths out of this sync "
        "(docs Phase 2 / code Phase 1 when listed)."
    )
    ui.bullet(
        "Agents remediate on edit via skill `astloom-standards-on-edit` "
        "so paths become syncable over time."
    )
    ui.blank()
    read = input_fn or _read_yes_no
    answer = read(
        "Skip syncing nonconforming docs/code this run? [y/N]: "
    ).strip().lower()
    if answer in {"y", "yes"}:
        result.skipped = True
        result.skipped_docs = list(docs)
        result.skipped_code = list(code)
        return apply_nonconforming_excludes(filters, docs=docs, code=code), result

    result.skipped = False
    return filters, result
