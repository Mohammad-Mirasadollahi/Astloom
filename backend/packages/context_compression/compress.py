"""Content-aware compressors (clean-room; not a Headroom source port)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


def _min_chars() -> int:
    raw = os.environ.get("ASTLOOM_CONTEXT_COMPRESS_MIN_CHARS", "2000").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 2000


def _max_string() -> int:
    raw = os.environ.get("ASTLOOM_CONTEXT_COMPRESS_MAX_STRING", "240").strip()
    try:
        return max(32, int(raw))
    except ValueError:
        return 240


def _max_list() -> int:
    raw = os.environ.get("ASTLOOM_CONTEXT_COMPRESS_MAX_LIST", "24").strip()
    try:
        return max(4, int(raw))
    except ValueError:
        return 24


@dataclass(frozen=True)
class CompressResult:
    compressed: str
    content_type: str
    original_chars: int
    compressed_chars: int
    skipped: bool
    lossy: bool
    notes: tuple[str, ...] = ()

    @property
    def chars_saved(self) -> int:
        return max(0, self.original_chars - self.compressed_chars)

    def public(self) -> dict[str, Any]:
        return {
            "compressed": self.compressed,
            "content_type": self.content_type,
            "original_chars": self.original_chars,
            "compressed_chars": self.compressed_chars,
            "chars_saved": self.chars_saved,
            "skipped": self.skipped,
            "lossy": self.lossy,
            "notes": list(self.notes),
        }


WATERMARK = "[astloom_context:"


def compress_payload(
    payload: str,
    *,
    content_type: str = "auto",
    min_chars: int | None = None,
    record_metrics: bool = True,
) -> CompressResult:
    text = payload if isinstance(payload, str) else str(payload)
    original = len(text)
    threshold = _min_chars() if min_chars is None else max(1, int(min_chars))

    # HR-11: never double-compress already marked payloads.
    if WATERMARK in text:
        result = CompressResult(
            compressed=text,
            content_type=_detect(text, content_type),
            original_chars=original,
            compressed_chars=original,
            skipped=True,
            lossy=False,
            notes=("already_compressed",),
        )
        if record_metrics:
            from .metrics import record

            record(result)
        return result

    if original < threshold:
        result = CompressResult(
            compressed=text,
            content_type=_detect(text, content_type),
            original_chars=original,
            compressed_chars=original,
            skipped=True,
            lossy=False,
            notes=("below_threshold",),
        )
        if record_metrics:
            from .metrics import record

            record(result)
        return result

    kind = _detect(text, content_type)
    if kind == "json":
        result = _compress_json(text, original)
    else:
        result = _compress_text(text, original)
    if record_metrics:
        from .metrics import record

        record(result)
    return result


def _detect(text: str, content_type: str) -> str:
    ct = (content_type or "auto").strip().lower()
    if ct in {"json", "text"}:
        return ct
    stripped = text.lstrip()
    if stripped[:1] in {"{", "["}:
        try:
            json.loads(text)
            return "json"
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return "text"


def _compress_json(text: str, original: int) -> CompressResult:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return _compress_text(text, original)

    notes: list[str] = ["json_minify"]
    lossy = False
    max_str = _max_string()
    max_list = _max_list()

    def walk(node: Any, depth: int = 0) -> Any:
        nonlocal lossy
        if isinstance(node, dict):
            return {str(k): walk(v, depth + 1) for k, v in node.items()}
        if isinstance(node, list):
            if len(node) > max_list:
                lossy = True
                notes.append("list_truncated")
                head = [walk(x, depth + 1) for x in node[:max_list]]
                head.append({"_truncated": len(node) - max_list})
                return head
            return [walk(x, depth + 1) for x in node]
        if isinstance(node, str) and len(node) > max_str:
            lossy = True
            notes.append("string_truncated")
            keep = max_str // 2
            return f"{node[:keep]}…[{len(node)} chars]…{node[-keep:]}"
        return node

    shrunk = walk(data)
    out = json.dumps(shrunk, ensure_ascii=False, separators=(",", ":"), default=str)
    return CompressResult(
        compressed=out,
        content_type="json",
        original_chars=original,
        compressed_chars=len(out),
        skipped=False,
        lossy=lossy,
        notes=tuple(dict.fromkeys(notes)),
    )


def _compress_text(text: str, original: int) -> CompressResult:
    # Keep head + tail; drop middle for logs.
    keep = max(400, original // 10)
    if original <= keep * 2:
        compact = "\n".join(line.rstrip() for line in text.splitlines())
        return CompressResult(
            compressed=compact,
            content_type="text",
            original_chars=original,
            compressed_chars=len(compact),
            skipped=False,
            lossy=compact != text,
            notes=("whitespace_normalize",) if compact != text else ("text_passthrough",),
        )
    mid = original - keep * 2
    out = f"{text[:keep]}\n…[{mid} chars omitted]…\n{text[-keep:]}"
    return CompressResult(
        compressed=out,
        content_type="text",
        original_chars=original,
        compressed_chars=len(out),
        skipped=False,
        lossy=True,
        notes=("text_head_tail",),
    )
