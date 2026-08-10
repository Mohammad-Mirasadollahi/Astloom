"""ADR 48 / feature 49: IDE-semantic edit-session use cases (LSP; not durable SoR)."""

from __future__ import annotations

from typing import Any, Callable

from ..domain.edit_session import (
    EditSessionPort,
    IdeDefinitionResult,
    IdeReferencesResult,
    IdeRenameResult,
    build_default_edit_session,
)
from ..domain.edit_session.servers import normalize_edit_language
from ..domain.errors import ValidationError
from ..domain.languages import detect_language_from_path
from ..domain.models import Scope
from ..domain.parsing_authority import SESSION_EDGE_REFERENCE_KIND
from .support import GraphServiceSupport

EditSessionFactory = Callable[..., EditSessionPort | None]


class EditSessionUseCases(GraphServiceSupport):
    """Session-scoped LSP tools; never write CODE_REL from LSP payloads."""

    edit_session_factory: EditSessionFactory | None

    def _factory(self) -> EditSessionFactory:
        factory = getattr(self, "edit_session_factory", None)
        if factory is None:
            return build_default_edit_session
        return factory

    def _unavailable(self, *, language: str, detail: str) -> dict[str, Any]:
        return {
            "available": False,
            "reference_kind": SESSION_EDGE_REFERENCE_KIND,
            "language": language,
            "detail": detail,
            "locations": [],
            "count": 0,
        }

    def ide_references(
        self,
        *,
        root_path: str,
        file_path: str,
        line: int,
        character: int,
        language: str = "",
    ) -> dict[str, Any]:
        lang = normalize_edit_language(
            language or detect_language_from_path(file_path) or "",
            file_path,
        )
        session = self._factory()(root_path=root_path, language=lang, file_path=file_path)
        if session is None:
            return self._unavailable(
                language=lang,
                detail=f"no local language server for {lang}; set ASTLOOM_LSP_CMD_* or install LS",
            )
        try:
            result: IdeReferencesResult = session.find_references(
                root_path=root_path,
                file_path=file_path,
                line=line,
                character=character,
                language=lang,
            )
            return result.to_dict()
        finally:
            session.close()

    def ide_definition(
        self,
        *,
        root_path: str,
        file_path: str,
        line: int,
        character: int,
        language: str = "",
    ) -> dict[str, Any]:
        lang = normalize_edit_language(
            language or detect_language_from_path(file_path) or "",
            file_path,
        )
        session = self._factory()(root_path=root_path, language=lang, file_path=file_path)
        if session is None:
            return self._unavailable(
                language=lang,
                detail=f"no local language server for {lang}; set ASTLOOM_LSP_CMD_* or install LS",
            )
        try:
            result: IdeDefinitionResult = session.goto_definition(
                root_path=root_path,
                file_path=file_path,
                line=line,
                character=character,
                language=lang,
            )
            return result.to_dict()
        finally:
            session.close()

    def ide_rename(
        self,
        *,
        root_path: str,
        file_path: str,
        line: int,
        character: int,
        new_name: str,
        language: str = "",
        apply: bool = True,
        scope: Scope | None = None,
        actor_id: str = "agent",
        correlation_id: str = "",
        idempotency_key: str = "",
        run_sync: bool = True,
    ) -> dict[str, Any]:
        lang = normalize_edit_language(
            language or detect_language_from_path(file_path) or "",
            file_path,
        )
        session = self._factory()(root_path=root_path, language=lang, file_path=file_path)
        if session is None:
            return {
                "available": False,
                "applied": False,
                "reference_kind": SESSION_EDGE_REFERENCE_KIND,
                "language": lang,
                "detail": f"no local language server for {lang}; set ASTLOOM_LSP_CMD_* or install LS",
                "changed_files": [],
                "reconcile": {},
            }
        try:
            result: IdeRenameResult = session.rename_symbol(
                root_path=root_path,
                file_path=file_path,
                line=line,
                character=character,
                new_name=new_name,
                language=lang,
                apply=apply,
            )
            payload = result.to_dict()
            if result.applied and result.changed_files and run_sync:
                if scope is None:
                    raise ValidationError("scope is required to reconcile after rename")
                reconcile = self.reconcile_after_edit(
                    list(result.changed_files),
                    scope=scope,
                    root_path=root_path,
                    actor_id=actor_id,
                    correlation_id=correlation_id or "ide-rename",
                    idempotency_key=idempotency_key or "ide-rename",
                    run_sync=True,
                )
                payload["reconcile"] = reconcile
            return payload
        finally:
            session.close()
