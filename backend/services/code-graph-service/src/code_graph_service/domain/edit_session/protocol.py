"""Edit-session port (session-scoped; not a graph Store)."""

from __future__ import annotations

from typing import Protocol

from .models import IdeDefinitionResult, IdeReferencesResult, IdeRenameResult


class EditSessionPort(Protocol):
    def find_references(
        self,
        *,
        root_path: str,
        file_path: str,
        line: int,
        character: int,
        language: str = "",
    ) -> IdeReferencesResult: ...

    def goto_definition(
        self,
        *,
        root_path: str,
        file_path: str,
        line: int,
        character: int,
        language: str = "",
    ) -> IdeDefinitionResult: ...

    def rename_symbol(
        self,
        *,
        root_path: str,
        file_path: str,
        line: int,
        character: int,
        new_name: str,
        language: str = "",
        apply: bool = True,
    ) -> IdeRenameResult: ...

    def close(self) -> None: ...
