"""`astloom context` — measure / stats for native context compression."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from astloom_cli.util import print_json, repo_root


def _metrics_path() -> Path:
    from astloom_cli.data_root import cache_dir

    return cache_dir(install_root=repo_root()) / "context-compression-metrics.json"


def _empty_metrics() -> dict[str, Any]:
    return {
        "calls": 0,
        "skipped": 0,
        "applied": 0,
        "lossy": 0,
        "original_chars": 0,
        "compressed_chars": 0,
        "chars_saved": 0,
        "pct_saved": 0.0,
        "by_content_type": {},
    }


def _load_persisted() -> dict[str, Any]:
    path = _metrics_path()
    if not path.is_file():
        return _empty_metrics()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_metrics()
    if not isinstance(data, dict):
        return _empty_metrics()
    out = _empty_metrics()
    for key in out:
        if key == "by_content_type":
            raw = data.get(key) or {}
            out[key] = {str(k): int(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
        elif key == "pct_saved":
            continue
        else:
            out[key] = int(data.get(key) or 0)
    saved = max(0, out["original_chars"] - out["compressed_chars"])
    out["chars_saved"] = saved
    out["pct_saved"] = (
        round(100.0 * saved / out["original_chars"], 2) if out["original_chars"] else 0.0
    )
    return out


def _persist_measure(report: dict[str, Any]) -> dict[str, Any]:
    cur = _load_persisted()
    cur["calls"] += 1
    cur["original_chars"] += int(report["original_chars"])
    cur["compressed_chars"] += int(report["compressed_chars"])
    if report.get("skipped"):
        cur["skipped"] += 1
    else:
        cur["applied"] += 1
    if report.get("lossy"):
        cur["lossy"] += 1
    kind = str(report.get("content_type") or "unknown")
    cur["by_content_type"][kind] = int(cur["by_content_type"].get(kind, 0)) + 1
    saved = max(0, cur["original_chars"] - cur["compressed_chars"])
    cur["chars_saved"] = saved
    cur["pct_saved"] = (
        round(100.0 * saved / cur["original_chars"], 2) if cur["original_chars"] else 0.0
    )
    path = _metrics_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cur, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return cur


def _read_payload(args: argparse.Namespace) -> str:
    if getattr(args, "payload", None):
        return str(args.payload)
    path = getattr(args, "file", None)
    if path:
        return Path(path).expanduser().read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit(
        "Provide --file PATH, --payload TEXT, or pipe stdin into `astloom context measure`"
    )


def _measure_report(payload: str, *, content_type: str, min_chars: int | None) -> dict:
    from context_compression import compress_payload

    result = compress_payload(
        payload,
        content_type=content_type,
        min_chars=min_chars,
        record_metrics=True,
    )
    pct = (
        round(100.0 * result.chars_saved / result.original_chars, 2)
        if result.original_chars
        else 0.0
    )
    return {
        "ok": True,
        "content_type": result.content_type,
        "original_chars": result.original_chars,
        "compressed_chars": result.compressed_chars,
        "chars_saved": result.chars_saved,
        "pct_saved": pct,
        "lossy": result.lossy,
        "skipped": result.skipped,
        "notes": list(result.notes),
        "ratio": (
            round(result.compressed_chars / result.original_chars, 4)
            if result.original_chars
            else 1.0
        ),
    }


def _print_human_measure(report: dict) -> None:
    print(f"content_type:     {report['content_type']}")
    print(f"original_chars:   {report['original_chars']}")
    print(f"compressed_chars: {report['compressed_chars']}")
    print(f"chars_saved:      {report['chars_saved']}")
    print(f"pct_saved:        {report['pct_saved']}%")
    print(f"ratio:            {report['ratio']}")
    print(f"lossy:            {report['lossy']}")
    print(f"skipped:          {report['skipped']}")
    if report.get("notes"):
        print(f"notes:            {', '.join(report['notes'])}")


def cmd_context_measure(args: argparse.Namespace) -> int:
    payload = _read_payload(args)
    min_chars = getattr(args, "min_chars", None)
    report = _measure_report(
        payload,
        content_type=str(getattr(args, "content_type", None) or "auto"),
        min_chars=int(min_chars) if min_chars is not None else None,
    )
    totals = _persist_measure(report)
    report["totals"] = totals
    if getattr(args, "json", False):
        print_json(report)
    else:
        _print_human_measure(report)
        print(f"totals_pct_saved: {totals['pct_saved']}% ({totals['calls']} calls)")
    return 0


def cmd_context_stats(args: argparse.Namespace) -> int:
    from context_compression import default_store, metrics_snapshot

    persisted = _load_persisted()
    report = {
        "ok": True,
        "cli_totals": persisted,
        "metrics_file": str(_metrics_path()),
        "this_process": metrics_snapshot(),
        "store_entries": default_store().stats()["entries"],
        "note": "cli_totals accumulate from `astloom context measure`; MCP uses astloom_context_stats",
    }
    if getattr(args, "json", False):
        print_json(report)
    else:
        m = persisted
        print(f"metrics_file:     {report['metrics_file']}")
        print(f"calls:            {m['calls']}")
        print(f"applied:          {m['applied']}")
        print(f"skipped:          {m['skipped']}")
        print(f"lossy:            {m['lossy']}")
        print(f"original_chars:   {m['original_chars']}")
        print(f"compressed_chars: {m['compressed_chars']}")
        print(f"chars_saved:      {m['chars_saved']}")
        print(f"pct_saved:        {m['pct_saved']}%")
        if m.get("by_content_type"):
            print(f"by_content_type:  {m['by_content_type']}")
        print(f"note:             {report['note']}")
    return 0
