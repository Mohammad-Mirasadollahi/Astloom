"""HTTP client call extraction for HTTP_CALLS edges (Codebase-Memory hybrid Wave C)."""

from __future__ import annotations

import re
from dataclasses import dataclass


# Python httpx / requests: client.get("...") / requests.post('...')
_PY_HTTP = re.compile(
    r"(?P<client>\b(?:requests|httpx|client|session|aiohttp)\b(?:\.\w+)*)\."
    r"(?P<method>get|post|put|delete|patch|head|options|request)\(\s*"
    r"(?:method\s*=\s*)?[\"'](?P<url>[^\"']+)[\"']",
    re.IGNORECASE | re.MULTILINE,
)

# JS/TS: fetch("/path") or axios.get('/x') or client.post("`")
_JS_FETCH = re.compile(
    r"\bfetch\(\s*[\"'`](?P<url>[^\"'`]+)[\"'`]",
    re.MULTILINE,
)
_JS_AXIOS = re.compile(
    r"\b(?:axios|client|api)\.(?P<method>get|post|put|delete|patch|head|options)\(\s*"
    r"[\"'`](?P<url>[^\"'`]+)[\"'`]",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class ExtractedHttpCall:
    method: str
    url_or_path: str
    framework: str
    line_hint: int = 0
    caller_hint: str = ""
    is_async: bool = False


def extract_http_calls(source: str, *, language: str, file_path: str = "") -> list[ExtractedHttpCall]:
    """Deterministic client HTTP call sites (no LLM)."""
    lang = (language or "").lower().strip()
    if lang in {"python", "py"}:
        return _extract_python(source)
    if lang in {"javascript", "js", "typescript", "ts", "tsx", "jsx"}:
        return _extract_js(source)
    _ = file_path
    return []


def normalize_http_path(url_or_path: str) -> str:
    """Normalize URL/path for matching ROUTE symbols."""
    raw = (url_or_path or "").strip()
    if not raw:
        return ""
    # Strip scheme+host
    if "://" in raw:
        raw = raw.split("://", 1)[1]
        if "/" in raw:
            raw = "/" + raw.split("/", 1)[1]
        else:
            raw = "/"
    if not raw.startswith("/"):
        raw = "/" + raw
    # Drop query/fragment
    raw = raw.split("?", 1)[0].split("#", 1)[0]
    return raw.rstrip("/") or "/"


def _line_is_async(source: str, pos: int) -> bool:
    line_start = source.rfind("\n", 0, pos) + 1
    line = source[line_start : source.find("\n", pos)]
    return bool(re.search(r"\bawait\b|\basync\b", line))


def _extract_python(source: str) -> list[ExtractedHttpCall]:
    out: list[ExtractedHttpCall] = []
    for match in _PY_HTTP.finditer(source):
        method = (match.group("method") or "GET").upper()
        if method == "REQUEST":
            method = "ANY"
        url = match.group("url")
        line = source[: match.start()].count("\n") + 1
        client = (match.group("client") or "requests").split(".", 1)[0].lower()
        framework = "httpx" if "httpx" in client else "requests" if "requests" in client else client
        is_async = framework in {"httpx", "aiohttp"} or _line_is_async(source, match.start())
        out.append(
            ExtractedHttpCall(
                method=method,
                url_or_path=url,
                framework=framework,
                line_hint=line,
                is_async=is_async,
            )
        )
    return out


def _extract_js(source: str) -> list[ExtractedHttpCall]:
    out: list[ExtractedHttpCall] = []
    for match in _JS_FETCH.finditer(source):
        url = match.group("url")
        line = source[: match.start()].count("\n") + 1
        out.append(
            ExtractedHttpCall(
                method="GET",
                url_or_path=url,
                framework="fetch",
                line_hint=line,
                is_async=_line_is_async(source, match.start()),
            )
        )
    for match in _JS_AXIOS.finditer(source):
        method = (match.group("method") or "get").upper()
        url = match.group("url")
        line = source[: match.start()].count("\n") + 1
        out.append(
            ExtractedHttpCall(
                method=method,
                url_or_path=url,
                framework="axios",
                line_hint=line,
                is_async=_line_is_async(source, match.start()),
            )
        )
    return out
