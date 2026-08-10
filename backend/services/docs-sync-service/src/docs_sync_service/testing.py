"""In-memory Docs Sync Store for unit/contract tests (thread-safe).

Role: deterministic Store fake for docs-sync service and CLI Phase-2 tests.
Source of truth: in-process dicts under one ``RLock`` so parallel workers cannot
corrupt maps. Allowed: concurrent Phase-2 tests without a CLI write lock.
Forbidden: sharing unlocked dicts across threads; production durability.
"""

from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any, Callable, TypeVar

from .errors import ConflictError, NotFoundError
from .models import (
    CodeSymbol,
    DocAnchor,
    Document,
    DocumentationDraft,
    DriftFinding,
    Scope,
)
from .util import digest

_T = TypeVar("_T")


class InMemoryStore:
    """Deterministic Store fake for unit and transport-contract tests."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._symbols: dict[str, CodeSymbol] = {}
        self._documents: dict[tuple[str, str, str, str], Document] = {}
        self._anchors: dict[str, DocAnchor] = {}
        self._findings: dict[str, DriftFinding] = {}
        self._drafts: dict[str, DocumentationDraft] = {}
        self._idempotency: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._events: list[dict[str, Any]] = []

    def _with_lock(self, fn: Callable[[], _T]) -> _T:
        with self._lock:
            return fn()

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id, scope.project_group_id or ""))

    @staticmethod
    def _document_key(document_id: str, scope: Scope) -> tuple[str, str, str, str]:
        return (scope.tenant_id, scope.workspace_id, scope.project_id, document_id)

    @staticmethod
    def _same_project(left: Scope, right: Scope) -> bool:
        return (left.tenant_id, left.workspace_id, left.project_id) == (right.tenant_id, right.workspace_id, right.project_id)

    def get_symbol(self, symbol_id: str, scope: Scope) -> CodeSymbol:
        def _run() -> CodeSymbol:
            item = self._symbols.get(symbol_id)
            if item is None or not self._same_project(item.scope, scope):
                raise NotFoundError("symbol not found in project scope")
            return deepcopy(item)

        return self._with_lock(_run)

    def find_symbol(self, scope: Scope, repo: str, file_path: str, symbol_path: str) -> CodeSymbol | None:
        def _run() -> CodeSymbol | None:
            for item in self._symbols.values():
                if (
                    self._same_project(item.scope, scope)
                    and item.repo == repo
                    and item.file_path == file_path
                    and item.symbol_path == symbol_path
                ):
                    return deepcopy(item)
            return None

        return self._with_lock(_run)

    def put_symbol(self, symbol: CodeSymbol) -> None:
        self._with_lock(lambda: self._symbols.__setitem__(symbol.id, deepcopy(symbol)))

    def delete_symbol(self, symbol_id: str, scope: Scope) -> None:
        def _run() -> None:
            item = self._symbols.get(symbol_id)
            if item is not None and self._same_project(item.scope, scope):
                del self._symbols[symbol_id]
            for aid, anchor in list(self._anchors.items()):
                if anchor.symbol_id == symbol_id and self._same_project(anchor.scope, scope):
                    del self._anchors[aid]

        self._with_lock(_run)

    def list_symbols(self, scope: Scope) -> list[CodeSymbol]:
        def _run() -> list[CodeSymbol]:
            items = [item for item in self._symbols.values() if self._same_project(item.scope, scope)]
            return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

        return self._with_lock(_run)

    def get_document(self, document_id: str, scope: Scope) -> Document:
        def _run() -> Document:
            item = self._documents.get(self._document_key(document_id, scope))
            if item is None:
                raise NotFoundError("document not found in project scope")
            return deepcopy(item)

        return self._with_lock(_run)

    def put_document(self, document: Document) -> None:
        self._with_lock(
            lambda: self._documents.__setitem__(
                self._document_key(document.id, document.scope),
                deepcopy(document),
            )
        )

    def list_documents(self, scope: Scope) -> list[Document]:
        def _run() -> list[Document]:
            items = [item for item in self._documents.values() if self._same_project(item.scope, scope)]
            return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

        return self._with_lock(_run)

    def get_anchor(self, anchor_id: str, scope: Scope) -> DocAnchor:
        def _run() -> DocAnchor:
            item = self._anchors.get(anchor_id)
            if item is None or not self._same_project(item.scope, scope):
                raise NotFoundError("anchor not found in project scope")
            return deepcopy(item)

        return self._with_lock(_run)

    def put_anchor(self, anchor: DocAnchor) -> None:
        self._with_lock(lambda: self._anchors.__setitem__(anchor.id, deepcopy(anchor)))

    def delete_anchor(self, anchor_id: str, scope: Scope) -> None:
        def _run() -> None:
            item = self._anchors.get(anchor_id)
            if item is not None and self._same_project(item.scope, scope):
                del self._anchors[anchor_id]

        self._with_lock(_run)

    def list_anchors(self, scope: Scope, symbol_id: str | None = None) -> list[DocAnchor]:
        def _run() -> list[DocAnchor]:
            items = [item for item in self._anchors.values() if self._same_project(item.scope, scope)]
            if symbol_id is not None:
                items = [item for item in items if item.symbol_id == symbol_id]
            return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

        return self._with_lock(_run)

    def get_finding(self, finding_id: str, scope: Scope) -> DriftFinding:
        def _run() -> DriftFinding:
            item = self._findings.get(finding_id)
            if item is None or not self._same_project(item.scope, scope):
                raise NotFoundError("drift finding not found in project scope")
            return deepcopy(item)

        return self._with_lock(_run)

    def put_finding(self, finding: DriftFinding) -> None:
        self._with_lock(lambda: self._findings.__setitem__(finding.id, deepcopy(finding)))

    def list_findings(self, scope: Scope) -> list[DriftFinding]:
        def _run() -> list[DriftFinding]:
            items = [item for item in self._findings.values() if self._same_project(item.scope, scope)]
            return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

        return self._with_lock(_run)

    def get_draft(self, draft_id: str, scope: Scope) -> DocumentationDraft:
        def _run() -> DocumentationDraft:
            item = self._drafts.get(draft_id)
            if item is None or not self._same_project(item.scope, scope):
                raise NotFoundError("documentation draft not found in project scope")
            return deepcopy(item)

        return self._with_lock(_run)

    def put_draft(self, draft: DocumentationDraft) -> None:
        self._with_lock(lambda: self._drafts.__setitem__(draft.id, deepcopy(draft)))

    def list_drafts(self, scope: Scope) -> list[DocumentationDraft]:
        def _run() -> list[DocumentationDraft]:
            items = [item for item in self._drafts.values() if self._same_project(item.scope, scope)]
            return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

        return self._with_lock(_run)

    def idempotent(self, scope: Scope, command: str, key: str, payload: dict[str, Any]) -> str | None:
        def _run() -> str | None:
            remembered = self._idempotency.get((self._scope_key(scope), command, key))
            if remembered is None:
                return None
            fingerprint, record_id = remembered
            if fingerprint != digest(payload):
                raise ConflictError("idempotency key was reused with a different payload")
            return record_id

        return self._with_lock(_run)

    def remember(self, scope: Scope, command: str, key: str, payload: dict[str, Any], record_id: str) -> None:
        self._with_lock(
            lambda: self._idempotency.__setitem__(
                (self._scope_key(scope), command, key),
                (digest(payload), record_id),
            )
        )

    def event(self, payload: dict[str, Any]) -> None:
        self._with_lock(lambda: self._events.append(deepcopy(payload)))

    def outbox(self) -> list[dict[str, Any]]:
        def _run() -> list[dict[str, Any]]:
            return deepcopy(sorted(self._events, key=lambda event: (event["occurred_at"], event["event_id"])))

        return self._with_lock(_run)
