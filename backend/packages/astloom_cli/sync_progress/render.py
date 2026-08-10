"""Console rendering for sync progress blocks."""

from __future__ import annotations

from typing import Any

from astloom_cli import ui
from astloom_cli.sync_progress.formatters import format_bar, format_duration, wall_clock_now


def print_progress_line(snap: dict[str, Any]) -> None:
    status = str(snap.get("status") or "")
    file_name = str(snap.get("file") or "")
    if len(file_name) > 48:
        file_name = "…" + file_name[-47:]
    logged_at = str(snap.get("logged_at") or wall_clock_now())
    elapsed_txt = format_duration(float(snap["elapsed_sec"]))
    print()
    print(
        f"   {ui.dim('at')} {logged_at}  "
        f"{ui.dim('elapsed')} {elapsed_txt}"
    )
    # Pre-queue Neo4j/discovery warmup: heartbeat only (no fake 0/0 percent).
    if status in {"preparing", "discovering", "loading"} and int(snap.get("total") or 0) == 0:
        detail = file_name or status
        print(f"   {ui.accent('…')}  {ui.bold(status)}  {ui.dim(detail)}")
        print()
        return
    pct = float(snap["percent"])
    bar = format_bar(pct)
    eta = snap.get("eta_sec")
    eta_txt = (
        "…"
        if eta is None and snap["done"] < snap["total"]
        else format_duration(float(eta or 0))
    )
    rate = snap.get("files_per_sec")
    basis = str(snap.get("rate_basis") or "")
    if rate:
        rate_txt = f"{rate:.2f}/s"
        if basis:
            rate_txt += f" ({basis})"
    else:
        rate_txt = "…"
    phase = str(snap.get("phase") or "ingest")
    if phase == "docs":
        run_label = "docs"
    elif phase == "embeddings":
        run_label = "embeddings"
    else:
        run_label = "code"
    line = (
        f"   {ui.accent(bar)} {ui.bold(f'{pct:5.1f}%')}  "
        f"{run_label} {snap['done']}/{snap['total']}  "
        f"ETA {eta_txt}  "
        f"rate {rate_txt}"
    )
    print(line)
    # Only show work this run will process — never prior/already-synced counts.
    q_new = int(snap.get("queue_new") or 0)
    q_changed = int(snap.get("queue_changed") or 0)
    q_unchanged = int(snap.get("queue_unchanged") or 0)
    # Code lang_backfill / docs link-refresh of body-stable linked docs.
    recheck_label = "link_refresh" if phase == "docs" else "lang_backfill"
    parts: list[str] = []
    if q_new:
        parts.append(f"new={q_new}")
    if q_changed:
        parts.append(f"changed={q_changed}")
    if q_unchanged:
        parts.append(f"{recheck_label}={q_unchanged}")
    if parts and phase != "embeddings":
        print(f"   {ui.dim('queue')} {'  '.join(parts)}")
        if int(snap["done"]) == 0 and int(snap.get("files_in_flight") or 0) > 0:
            print(
                f"   {ui.dim('note')} 0 of {snap['total']} files finished yet "
                f"(in-flight not counted until each file completes)"
            )
    if phase == "docs":
        detail = (
            f"   {ui.dim('docs')} indexed={snap.get('docs_indexed', snap.get('done'))}  "
            f"{ui.dim('links')} {snap.get('links_created', 0)}  "
            f"{ui.dim('anchors')} {snap.get('anchors_registered', 0)}"
        )
    elif phase == "embeddings":
        detail = (
            f"   {ui.dim('embedding_refresh')} "
            f"refreshed={snap.get('embeddings_refreshed', snap.get('done'))}  "
            f"{ui.dim('model')} {snap.get('file') or '…'}"
        )
    else:
        detail = (
            f"   {ui.dim('symbols')} {snap.get('symbols_indexed')}  "
            f"{ui.dim('edges')} {snap.get('edges_written')}  "
            f"{ui.dim('≈tokens (local chars÷4 estimate)')} {snap.get('approx_tokens')}"
        )
    if file_name:
        detail += f"  {ui.dim('file')} {file_name}"
    print(detail)

    in_flight = int(snap.get("files_in_flight") or 0)
    workers = int(snap.get("file_workers") or 0)
    rpm = int(snap.get("rpm") or 0)
    rpm_cap = int(snap.get("rpm_inflight_cap") or rpm or 0)
    rpm_inf = int(snap.get("rpm_inflight") or 0)
    rpm_starts = int(snap.get("rpm_starts_in_window") or 0)
    if workers or in_flight or rpm:
        conc = (
            f"   {ui.dim('parallel')} {in_flight} active / {workers or '?'} workers"
        )
        paths = list(snap.get("files_in_flight_paths") or [])
        if paths:
            shown = ", ".join(str(p) for p in paths[:4])
            if len(paths) > 4:
                shown += ", …"
            conc += f"  [{shown}]"
        print(conc)
        if rpm:
            print(
                f"   {ui.dim('rpm')} inflight {rpm_inf}/{rpm_cap or rpm}  "
                f"starts {rpm_starts}/{rpm} (rolling 60s)"
            )
    print()
