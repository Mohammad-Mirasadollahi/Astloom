"""Per-language file counts and cross-root merge."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from astloom_cli.commands.inventory.util import norm_rel, pct


def language_breakdown(
    discovered_code: list[Any],
    *,
    done: set[str] | list[str],
    edited: set[str] | list[str],
    remaining: set[str] | list[str],
) -> list[dict[str, Any]]:
    """Per-language file counts, bytes, and processing status among discovered code."""
    done_set = {norm_rel(p) for p in done}
    edited_set = {norm_rel(p) for p in edited}
    remaining_set = {norm_rel(p) for p in remaining}
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "files": 0,
            "bytes": 0,
            "done_count": 0,
            "edited_count": 0,
            "remaining_count": 0,
        }
    )
    for item in discovered_code:
        rel = norm_rel(item.relative_path)
        lang = str(getattr(item, "language", None) or "unknown").strip() or "unknown"
        row = buckets[lang]
        row["files"] += 1
        row["bytes"] += int(getattr(item, "size_bytes", 0) or 0)
        if rel in done_set:
            row["done_count"] += 1
        elif rel in edited_set:
            row["edited_count"] += 1
        elif rel in remaining_set:
            row["remaining_count"] += 1
        else:
            row["remaining_count"] += 1
    return _finalize_language_rows(buckets)


def merge_language_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sum per-root language rows into one table."""
    merged: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "files": 0,
            "bytes": 0,
            "done_count": 0,
            "edited_count": 0,
            "remaining_count": 0,
        }
    )
    for row in results:
        for item in row.get("languages") or []:
            lang = str(item.get("language") or "unknown")
            bucket_row = merged[lang]
            for key in ("files", "bytes", "done_count", "edited_count", "remaining_count"):
                bucket_row[key] += int(item.get(key) or 0)
    return _finalize_language_rows(merged)


def _finalize_language_rows(buckets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    total_files = sum(int(b["files"]) for b in buckets.values())
    total_bytes = sum(int(b["bytes"]) for b in buckets.values())
    out: list[dict[str, Any]] = []
    for language, row in sorted(buckets.items(), key=lambda kv: (-int(kv[1]["files"]), kv[0])):
        files = int(row["files"])
        nbytes = int(row["bytes"])
        out.append(
            {
                "language": language,
                "files": files,
                "bytes": nbytes,
                "percent_of_code": pct(files, total_files),
                "percent_of_bytes": pct(nbytes, total_bytes),
                "done_count": int(row["done_count"]),
                "edited_count": int(row["edited_count"]),
                "remaining_count": int(row["remaining_count"]),
                "percent_done": pct(int(row["done_count"]), files),
                "percent_edited": pct(int(row["edited_count"]), files),
                "percent_remaining": pct(int(row["remaining_count"]), files),
            }
        )
    return out
