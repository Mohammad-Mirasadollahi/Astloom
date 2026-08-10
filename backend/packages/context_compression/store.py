"""
Module contract: tenant-scoped TTL cache for compressed context originals.

Role: Store originals under opaque handles; retrieve only when scope matches.
SoT/invariants: Key = scope_fingerprint + handle; expired entries are gone.
Allowed failures: miss / expired / wrong scope → None (caller maps to error).
Forbidden: cross-scope retrieve; durable disk without ADR; cloud sync.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    original: str
    scope_key: str
    expires_at: float
    content_type: str
    lossy: bool


class ContextCompressionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, _Entry] = {}

    @staticmethod
    def scope_key(scope: dict[str, str]) -> str:
        parts = (
            str(scope.get("tenant_id") or "").strip(),
            str(scope.get("workspace_id") or "").strip(),
            str(scope.get("project_id") or "").strip(),
        )
        return "|".join(parts)

    def put(
        self,
        original: str,
        *,
        scope: dict[str, str],
        content_type: str,
        lossy: bool,
        ttl_seconds: int = 3600,
    ) -> str:
        sk = self.scope_key(scope)
        handle = "acc1." + hashlib.sha256(
            f"{sk}:{secrets.token_hex(16)}:{len(original)}".encode()
        ).hexdigest()[:40]
        ttl = max(60, min(int(ttl_seconds), 86400))
        with self._lock:
            self._purge_locked()
            self._items[handle] = _Entry(
                original=original,
                scope_key=sk,
                expires_at=time.time() + ttl,
                content_type=content_type,
                lossy=lossy,
            )
        return handle

    def get(self, handle: str, *, scope: dict[str, str]) -> dict[str, Any] | None:
        sk = self.scope_key(scope)
        with self._lock:
            self._purge_locked()
            entry = self._items.get(handle)
            if entry is None:
                return None
            if entry.scope_key != sk:
                return None
            return {
                "handle": handle,
                "payload": entry.original,
                "content_type": entry.content_type,
                "lossy": entry.lossy,
                "chars": len(entry.original),
            }

    def stats(self) -> dict[str, int]:
        with self._lock:
            self._purge_locked()
            return {"entries": len(self._items)}

    def _purge_locked(self) -> None:
        now = time.time()
        dead = [h for h, e in self._items.items() if e.expires_at <= now]
        for h in dead:
            del self._items[h]


_DEFAULT: ContextCompressionStore | None = None
_DEFAULT_LOCK = threading.Lock()


def default_store() -> ContextCompressionStore:
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = ContextCompressionStore()
        return _DEFAULT
