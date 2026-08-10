"""Per-root usage task rows and sync-complete UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astloom_cli import ui
from astloom_cli.sync_usage_log import estimate_output_tokens, task_entry


def build_usage_tasks(
    *,
    root_path: Path,
    payload: dict[str, Any],
    docs_payload: dict[str, Any],
    ingest_sec: float,
    docs_sec: float,
    tokens_in: int,
    docs_tokens_in: int,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = [
        task_entry(
            name=f"code_sync:{root_path}",
            duration_sec=ingest_sec,
            tokens_in=tokens_in,
            tokens_out=estimate_output_tokens(
                symbols_documented=int(payload.get("symbols_documented") or 0),
            ),
        )
    ]
    if docs_payload:
        tasks.append(
            task_entry(
                name=f"docs_link:{root_path}",
                duration_sec=docs_sec,
                tokens_in=docs_tokens_in,
                tokens_out=estimate_output_tokens(
                    symbols_documented=0,
                    docs_indexed=int(docs_payload.get("docs_indexed") or 0),
                ),
            )
        )
    outcomes = list(payload.get("outcomes") or [])
    sym_total = sum(int(o.get("symbols_indexed") or 0) for o in outcomes) or 1
    for item in outcomes:
        share = int(item.get("symbols_indexed") or 0) / sym_total
        file_in = int(tokens_in * share)
        file_out = estimate_output_tokens(
            symbols_documented=int(item.get("symbols_documented") or 0),
        )
        tasks.append(
            task_entry(
                name=f"file:{item.get('relative_path') or item.get('file_id') or '?'}",
                duration_sec=ingest_sec * share,
                tokens_in=file_in,
                tokens_out=file_out,
                extra={
                    "status": item.get("status"),
                    "language": item.get("language"),
                    "symbols_indexed": item.get("symbols_indexed"),
                },
            )
        )
    return tasks


def print_sync_complete(
    *,
    svc: Any,
    payload: dict[str, Any],
    docs_payload: dict[str, Any],
    tokens_in: int,
    docs_tokens_in: int,
    tokens_out: int,
    ingest_sec: float,
    docs_sec: float,
) -> None:
    ui.blank()
    ui.heading("Sync complete")
    ui.blank()
    ui.kv("Mode", str(payload.get("mode")))
    refresh_mode = str(payload.get("embedding_refresh_mode") or "").strip()
    if refresh_mode:
        ui.kv("Embedding mode", refresh_mode)
    ui.kv("Truncated", str(payload.get("truncated")))
    ui.kv("Files", f"ingested={payload.get('files_ingested')}  discovered={payload.get('files_discovered')}")
    ui.kv("Symbols", f"indexed={payload.get('symbols_indexed')}  changed={payload.get('symbols_changed')}")
    refresh = payload.get("embedding_refresh") or {}
    if refresh:
        reasons = refresh.get("reasons") or {}
        deferred = int(reasons.get("deferred_over_max_pending") or 0)
        ui.kv(
            "Embeddings",
            (
                f"state={refresh.get('state')}  "
                f"refreshed={refresh.get('refreshed')}  "
                f"scanned={refresh.get('scanned')}  "
                f"orphans={refresh.get('deleted_orphans')}  "
                f"deferred={deferred}"
            ),
        )
        if refresh.get("error"):
            ui.kv("Embedding error", str(refresh.get("error"))[:200])
    try:
        final_rpm = svc.llm_sessions_snapshot() if hasattr(svc, "llm_sessions_snapshot") else {}
    except Exception:  # noqa: BLE001
        final_rpm = {}
    if final_rpm.get("rpm"):
        ui.kv(
            "RPM final",
            f"inflight {int(final_rpm.get('inflight_count') or 0)}/"
            f"{int(final_rpm.get('inflight_cap') or final_rpm.get('rpm') or 0)}  "
            f"starts {int(final_rpm.get('starts_in_window') or 0)}/{int(final_rpm.get('rpm') or 0)}  "
            f"history {len(final_rpm.get('history') or [])}",
        )
    ui.kv(
        "Tokens≈",
        f"in={tokens_in + docs_tokens_in}  out={tokens_out}  "
        f"total={tokens_in + docs_tokens_in + tokens_out}  "
        f"({ingest_sec + docs_sec:.1f}s)",
    )
    if payload.get("hint"):
        ui.blank()
        ui.section("Hint")
        ui.bullet(str(payload["hint"]))
