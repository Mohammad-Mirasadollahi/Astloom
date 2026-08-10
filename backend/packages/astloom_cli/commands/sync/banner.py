"""Pre-ingest UI banner for one sync root (filters, CPU, RPM)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from astloom_cli import ui


def print_filters_banner(
    *,
    scope: Any,
    root_path: Path,
    args: argparse.Namespace,
    filters: dict[str, Any],
    standards_gate: Any,
    svc: Any,
) -> None:
    ui.blank()
    print(f"{ui.accent('→')}  Syncing {ui.scope_line(scope.tenant_id, scope.workspace_id, scope.project_id)}")
    ui.kv("Path", str(root_path))
    if str(getattr(args, "sync_mode", "") or "").strip().lower() == "heal":
        ui.kv(
            "Embeddings",
            "full-project heal after incremental file pass (missing/mismatch + orphans)",
        )
    else:
        ui.kv(
            "Embeddings",
            "touched files only (noop: capped backlog; use sync heal for full project)",
        )
    ui.kv("Progress", f"updates about every {int(args.progress_interval)}s (adapts ETA from observed rate)")
    if standards_gate.docs_nonconforming or standards_gate.code_nonconforming:
        ui.kv(
            "Standards gate",
            (
                f"skipped={standards_gate.skipped}  "
                f"docs_bad={len(standards_gate.docs_nonconforming)}  "
                f"docs_excluded={len(standards_gate.skipped_docs)}  "
                f"code_excluded={len(standards_gate.skipped_code)}"
            ),
        )
    rpm_snap: dict[str, Any] = {}
    try:
        if hasattr(svc, "llm_sessions_snapshot"):
            rpm_snap = svc.llm_sessions_snapshot() or {}
    except Exception:  # noqa: BLE001
        rpm_snap = {}
    rpm_limit = int(rpm_snap.get("rpm") or 0)
    try:
        from code_graph_service.locked_store import resolve_sync_cpu_plan

        plan = resolve_sync_cpu_plan()
        if plan.mode == "percent":
            ui.kv(
                "CPU budget",
                f"{plan.cpu_percent}% of {plan.cpu_count} CPUs → "
                f"{plan.workers} workers, {plan.embed_concurrency} embeds, "
                f"torch/OMP={plan.torch_threads}",
            )
        elif plan.mode == "workers":
            ui.kv(
                "CPU budget",
                f"explicit {plan.workers} workers "
                f"(embeds={plan.embed_concurrency}, torch/OMP={plan.torch_threads})",
            )
        else:
            ui.kv(
                "CPU budget",
                f"auto → {plan.workers} workers "
                f"(embeds≤{plan.embed_concurrency}, torch/OMP={plan.torch_threads}; "
                f"CPU×RPM)",
            )
    except Exception:  # noqa: BLE001
        pass
    if rpm_limit:
        ui.kv(
            "RPM",
            f"{rpm_limit} req/min  "
            f"(inflight cap {int(rpm_snap.get('inflight_cap') or rpm_limit)}; "
            f"live lines show active/starts)",
        )
    ui.kv("Config", ", ".join(filters["sources"]))
    if filters["include_paths"]:
        ui.kv("Only (legacy)", ", ".join(filters["include_paths"]))
    if filters.get("docs_enabled") and filters.get("doc_match_globs"):
        ui.kv("Docs match", ", ".join(filters["doc_match_globs"][:4]))
    n_dirs = len(filters["exclude_dirs"])
    n_globs = len(filters["exclude_globs"])
    sample = [d for d in filters["exclude_dirs"] if d not in {".git", "git"}][:4]
    sample_g = list(filters["exclude_globs"])[:3]
    bits = [f"{n_dirs} dirs"]
    if sample:
        bits.append(f"e.g. {', '.join(sample)}")
    bits.append(f"{n_globs} globs")
    if sample_g:
        bits.append(f"e.g. {', '.join(sample_g)}")
    ui.kv("Code exclude", " · ".join(bits))
    layered_n = len(filters.get("layered_ignore_globs") or [])
    rein_n = len(filters.get("layered_reinclude_globs") or [])
    if layered_n or rein_n or filters.get("layered_ignore_sources"):
        src = filters.get("layered_ignore_sources") or []
        ui.kv(
            "Layered ignore",
            f"{layered_n} exclude · {rein_n} reinclude"
            + (f" · {', '.join(Path(s).name for s in src)}" if src else ""),
        )
    ui.blank()
