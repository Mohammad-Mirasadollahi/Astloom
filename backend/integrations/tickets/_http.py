"""Shared HTTP helper for ticket tracker integrations."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def http_json(method: str, url: str, body: dict[str, Any] | None, *, headers: dict[str, str]) -> dict[str, Any]:
    payload = None if method.upper() == "GET" or body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=payload,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 — operator-configured vendor URL
            raw = response.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:300] if exc.fp else str(exc)
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("vendor response was not a JSON object")
    return parsed
