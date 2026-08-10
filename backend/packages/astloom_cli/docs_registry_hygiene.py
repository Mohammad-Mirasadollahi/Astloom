"""Purge known live-test fixture noise from docs-sync symbol registry.

Role: remove never_linked / ghost_* / never_should_exist rows left by live QA
so docs_status coverage is not polluted. Called from quality_audit and sync
follow-up (best-effort; never fails the caller).
"""

from __future__ import annotations

from typing import Any

# Substrings matched against "symbol_path file_path" (case-sensitive path norms).
_FIXTURE_MARKERS = (
    "never_linked",
    "ghost_",
    "never_should_exist",
)

_TRANSIENT_MARKERS = (
    "adminshutdown",
    "connectiondoesnotexist",
    "defunct connection",
    "terminating connection due to administrator command",
    "server closed the connection",
    "connection not open",
)


def is_docs_registry_fixture_noise(*, symbol_path: str, file_path: str = "") -> bool:
    """True when the docs-sync row looks like an intentional live-test fixture."""
    blob = f"{symbol_path or ''} {file_path or ''}"
    return any(marker in blob for marker in _FIXTURE_MARKERS)


def _is_transient_store_error(exc: BaseException) -> bool:
    blob = f"{type(exc).__name__}:{exc}".lower()
    return any(marker in blob for marker in _TRANSIENT_MARKERS)


def _reset_docs_store(docs_service: Any) -> None:
    store = getattr(docs_service, "store", None)
    if store is None:
        return
    reset = getattr(store, "reset_connections", None)
    if callable(reset):
        reset()
        return
    closer = getattr(store, "close", None)
    if callable(closer):
        closer()


def purge_docs_registry_fixture_noise(docs_service: Any, scope: Any) -> dict[str, Any]:
    """Unregister fixture-noise symbols in *scope*. Best-effort per row."""
    deleted: list[dict[str, str]] = []
    errors: list[str] = []

    def _list_symbols() -> list[Any]:
        return list(docs_service.store.list_symbols(scope))

    try:
        symbols = _list_symbols()
    except Exception as exc:  # noqa: BLE001
        if not _is_transient_store_error(exc):
            return {
                "deleted_count": 0,
                "deleted": [],
                "errors": [f"list_symbols: {type(exc).__name__}: {exc}"],
            }
        try:
            _reset_docs_store(docs_service)
            symbols = _list_symbols()
        except Exception as retry_exc:  # noqa: BLE001
            return {
                "deleted_count": 0,
                "deleted": [],
                "errors": [f"list_symbols: {type(retry_exc).__name__}: {retry_exc}"],
            }

    for symbol in symbols:
        path = str(getattr(symbol, "symbol_path", "") or "")
        file_path = str(getattr(symbol, "file_path", "") or "")
        if not is_docs_registry_fixture_noise(symbol_path=path, file_path=file_path):
            continue
        sid = str(getattr(symbol, "id", "") or "")
        if not sid:
            continue
        try:
            docs_service.unregister_symbol(scope, sid)
            deleted.append({"id": sid, "symbol_path": path, "file_path": file_path})
        except Exception as exc:  # noqa: BLE001
            if _is_transient_store_error(exc):
                try:
                    _reset_docs_store(docs_service)
                    docs_service.unregister_symbol(scope, sid)
                    deleted.append({"id": sid, "symbol_path": path, "file_path": file_path})
                    continue
                except Exception as retry_exc:  # noqa: BLE001
                    errors.append(f"{sid}: {type(retry_exc).__name__}: {retry_exc}")
                    continue
            errors.append(f"{sid}: {type(exc).__name__}: {exc}")

    return {
        "deleted_count": len(deleted),
        "deleted": deleted,
        "errors": errors,
    }
