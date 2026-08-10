"""Freshness / stale banners (Wave 3) and rationale comment extraction."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from time import time


_RATIONALE = re.compile(
    r"^\s*(?:#|//|/\*)\s*(?P<tag>WHY|NOTE|HACK|TODO|FIXME)\s*:\s*(?P<body>.+?)(?:\*/)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class RationaleHit:
    tag: str
    body: str
    line: int


@dataclass
class FreshnessState:
    """In-process pending file edits awaiting ingest/sync."""

    pending: dict[str, float] = field(default_factory=dict)  # path -> unix mtime noted
    last_sync_at: float = 0.0
    verified: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def mark_pending(self, file_path: str, *, now: float | None = None) -> None:
        with self._lock:
            self.pending[file_path.replace("\\", "/")] = float(now if now is not None else time())

    def mark_pending_many(self, file_paths: list[str], *, now: float | None = None) -> None:
        stamp = float(now if now is not None else time())
        with self._lock:
            for path in file_paths:
                cleaned = (path or "").strip().replace("\\", "/")
                if cleaned:
                    self.pending[cleaned] = stamp

    def clear_pending(self, file_path: str | None = None) -> None:
        with self._lock:
            if file_path is None:
                self.pending.clear()
            else:
                self.pending.pop(file_path.replace("\\", "/"), None)
            self.last_sync_at = time()
            self.verified = True

    def stale_banner(self, referenced_paths: list[str] | None = None) -> dict:
        referenced = {p.replace("\\", "/") for p in (referenced_paths or [])}
        with self._lock:
            pending_snapshot = dict(self.pending)
            last_sync = self.last_sync_at
            verified = self.verified
        pending_refs = sorted(p for p in pending_snapshot if p in referenced) if referenced else []
        other = (
            sorted(p for p in pending_snapshot if p not in referenced)
            if referenced
            else sorted(pending_snapshot)
        )
        banner = None
        footer = None
        if pending_refs:
            banner = (
                "⚠️ Pending sync: "
                + ", ".join(pending_refs[:8])
                + " — read those files directly for live content."
            )
        elif other:
            footer = f"Pending sync (not in this result): {', '.join(other[:5])}"
        status = "pending" if pending_snapshot else ("ok" if verified else "unknown")
        if status == "unknown":
            banner = (
                "⚠️ Freshness unknown: filesystem edits are not monitored in this "
                "process; run astloom sync before relying on graph absence."
            )
        return {
            "status": status,
            "is_stale": status != "ok",
            "pending_count": len(pending_snapshot),
            "pending_files": sorted(pending_snapshot)[:50],
            "banner": banner,
            "footer": footer,
            "last_sync_at": last_sync or None,
        }


def extract_rationale_comments(source: str) -> list[RationaleHit]:
    hits: list[RationaleHit] = []
    for match in _RATIONALE.finditer(source):
        line = source[: match.start()].count("\n") + 1
        hits.append(
            RationaleHit(
                tag=match.group("tag").upper(),
                body=match.group("body").strip(),
                line=line,
            )
        )
    return hits


_MODULE_DOC_MIN_CHARS = 40
_CONTRACT_HINT = re.compile(
    r"\b(source of truth|fail-?open|fail-?closed|durability|invariant|must not|"
    r"PostgreSQL|Redis|rebuild|wake|queue|lease|tenant)\b",
    re.IGNORECASE,
)


def extract_module_contract_docstring(source: str, language: str = "python") -> str | None:
    """Return a selective module-level contract docstring when present.

    Python uses ``ast.get_docstring``. Other languages: leading block comment only when
    it looks like a multi-line contract (length + keyword hints). Short one-liners skipped.
    """
    lang = (language or "python").strip().lower()
    text = source or ""
    if lang == "python":
        try:
            import ast

            tree = ast.parse(text)
            doc = ast.get_docstring(tree)
        except SyntaxError:
            return None
        if not doc:
            return None
        cleaned = doc.strip()
        if len(cleaned) < _MODULE_DOC_MIN_CHARS:
            return None
        return cleaned

    # JS/TS / C-like: opening /** ... */ or /* ... */ before first import/export/function
    block = re.match(r"^\s*/\*\*?(?P<body>.*?)\*/", text, re.DOTALL)
    if not block:
        return None
    body = re.sub(r"^\s*\*\s?", "", block.group("body"), flags=re.MULTILINE).strip()
    if len(body) < _MODULE_DOC_MIN_CHARS:
        return None
    if not _CONTRACT_HINT.search(body) and body.count("\n") < 2:
        return None
    return body
