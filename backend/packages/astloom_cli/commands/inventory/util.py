"""Inventory helpers: paths, percents, buckets, file rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

TOP_N = 10
DOCUMENTED = frozenset({"generated", "human"})
CODE_KINDS = frozenset({"function", "method", "class"})


def norm_rel(path: str) -> str:
    text = path.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def rel_under(root: Path, file_path: str) -> str | None:
    raw = (file_path or "").strip().replace("\\", "/")
    if not raw or raw.startswith("__astloom__/"):
        return None
    path = Path(raw)
    # Callers should pass an already-resolved root; resolve only if needed.
    resolved_root = root if root.is_absolute() else root.expanduser().resolve()
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(resolved_root)).replace("\\", "/")
        except ValueError:
            return None
    return norm_rel(raw)


def pct(done: int, total: int) -> float:
    if total <= 0:
        return 100.0 if done == 0 else 0.0
    return round(100.0 * done / total, 1)


def format_pending_work_line(block: dict[str, Any]) -> str:
    """Human count of files still needing sync (no fraction/percent noise)."""
    edited = int(block.get("edited_count") or 0)
    remaining = int(block.get("remaining_count") or 0)
    parts: list[str] = []
    if edited:
        parts.append(f"{edited} edited")
    if remaining:
        parts.append(f"{remaining} not indexed yet")
    return ", ".join(parts) if parts else "none"


def format_synced_beside_total(block: dict[str, Any], *, size_label: str = "") -> str:
    """Total size/count with already-synced count beside it."""
    total = int(block.get("total") or 0)
    done = int(block.get("done_count") or 0)
    head = size_label.strip() or f"{total} files"
    return f"{head} · {done} already synced"


def edited_percent_line(block: dict[str, Any]) -> str:
    """Back-compat alias — prefer ``format_pending_work_line``."""
    return format_pending_work_line(block)


def bucket(done: list[str], remaining: list[str]) -> dict[str, Any]:
    total = len(done) + len(remaining)
    return {
        "done_count": len(done),
        "remaining_count": len(remaining),
        "total": total,
        "percent_done": pct(len(done), total),
        "done": sorted(done),
        "remaining": sorted(remaining),
    }


def status_bucket(
    done: list[str],
    edited: list[str],
    remaining: list[str],
) -> dict[str, Any]:
    """Three-way coverage: up-to-date / edited (needs re-sync) / never ingested."""
    total = len(done) + len(edited) + len(remaining)
    return {
        "done_count": len(done),
        "edited_count": len(edited),
        "remaining_count": len(remaining),
        "total": total,
        "percent_done": pct(len(done), total),
        "percent_edited": pct(len(edited), total),
        "percent_remaining": pct(len(remaining), total),
        "done": sorted(done),
        "edited": sorted(edited),
        "remaining": sorted(remaining),
    }


def top(items: list[dict[str, Any]], *, n: int = TOP_N) -> list[dict[str, Any]]:
    return list(items[: max(0, int(n))])


def file_row(
    *,
    path: str,
    status: str,
    symbols: int = 0,
    documented: int = 0,
    embedding_eligible: int = 0,
    embedding_indexed: int = 0,
    embedding_missing: int = 0,
    embed_models: list[str] | None = None,
    docs_models: list[str] | None = None,
    category: str = "code",
    edit_reason: str = "",
) -> dict[str, Any]:
    embeds = sorted({m for m in (embed_models or []) if m})
    docs = sorted({m for m in (docs_models or []) if m})
    return {
        "file": path,
        "category": category,
        "status": status,
        "edit_reason": edit_reason,
        "symbols": int(symbols),
        "documented": int(documented),
        "embedding_eligible": int(embedding_eligible),
        "embedding_indexed": int(embedding_indexed),
        "embedding_missing": int(embedding_missing),
        "doc_percent": pct(documented, symbols) if symbols else (100.0 if documented == 0 else 0.0),
        "embed_models": embeds,
        "docs_models": docs,
        "models": sorted(set(embeds) | set(docs)),
    }


def sort_done(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (-int(r.get("documented") or 0), -int(r.get("symbols") or 0), str(r.get("file") or "")),
    )


def sort_remaining(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: str(r.get("file") or ""))
