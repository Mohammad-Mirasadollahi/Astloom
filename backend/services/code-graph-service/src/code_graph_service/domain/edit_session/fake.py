"""Deterministic in-memory edit session for unit tests (no real language server)."""

from __future__ import annotations

import re
from pathlib import Path

from ..errors import ValidationError
from .models import IdeDefinitionResult, IdeLocation, IdeReferencesResult, IdeRenameResult
from .workspace_edit import apply_workspace_edit, resolve_under_root


class FakeEditSession:
    """Simple name-based references/rename for fixtures — still IDE-semantic labeled."""

    def __init__(self, *, language: str = "python") -> None:
        self._language = language

    def close(self) -> None:
        return None

    def find_references(
        self,
        *,
        root_path: str,
        file_path: str,
        line: int,
        character: int,
        language: str = "",
    ) -> IdeReferencesResult:
        name = self._symbol_at(root_path, file_path, line, character)
        locs = self._find_name(root_path, name)
        return IdeReferencesResult(
            available=True,
            language=language or self._language,
            locations=locs,
            detail=f"fake references for {name}",
        )

    def goto_definition(
        self,
        *,
        root_path: str,
        file_path: str,
        line: int,
        character: int,
        language: str = "",
    ) -> IdeDefinitionResult:
        name = self._symbol_at(root_path, file_path, line, character)
        locs = self._find_name(root_path, name, definitions_only=True)
        return IdeDefinitionResult(
            available=True,
            language=language or self._language,
            locations=locs[:1],
            detail=f"fake definition for {name}",
        )

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
    ) -> IdeRenameResult:
        name = self._symbol_at(root_path, file_path, line, character)
        new = (new_name or "").strip()
        if not new:
            raise ValidationError("new_name is required")
        locs = self._find_name(root_path, name)
        changes: dict[str, list[dict]] = {}
        root = Path(root_path).resolve()
        for loc in locs:
            abs_path = (root / loc.file_path).resolve()
            uri = abs_path.as_uri()
            edits = changes.setdefault(uri, [])
            edits.append(
                {
                    "range": {
                        "start": {"line": loc.line, "character": loc.character},
                        "end": {
                            "line": loc.end_line if loc.end_line is not None else loc.line,
                            "character": loc.end_character
                            if loc.end_character is not None
                            else loc.character + len(name),
                        },
                    },
                    "newText": new,
                }
            )
        if not apply:
            return IdeRenameResult(
                available=True,
                applied=False,
                language=language or self._language,
                detail="apply=false",
            )
        changed = apply_workspace_edit(root_path, {"changes": changes})
        return IdeRenameResult(
            available=True,
            applied=True,
            language=language or self._language,
            changed_files=changed,
            detail=f"fake rename {name} -> {new}",
        )

    def _symbol_at(self, root_path: str, file_path: str, line: int, character: int) -> str:
        _, abs_path = resolve_under_root(root_path, file_path)
        text = abs_path.read_text(encoding="utf-8")
        lines = text.split("\n")
        if line < 0 or line >= len(lines):
            raise ValidationError("line out of range")
        row = lines[line]
        if character < 0 or character > len(row):
            raise ValidationError("character out of range")
        # Expand to identifier under cursor.
        start = character
        while start > 0 and (row[start - 1].isalnum() or row[start - 1] == "_"):
            start -= 1
        end = character
        while end < len(row) and (row[end].isalnum() or row[end] == "_"):
            end += 1
        name = row[start:end]
        if not name:
            raise ValidationError("no symbol under cursor")
        return name

    def _find_name(
        self,
        root_path: str,
        name: str,
        *,
        definitions_only: bool = False,
    ) -> list[IdeLocation]:
        root = Path(root_path).resolve()
        pattern = re.compile(rf"\b{re.escape(name)}\b")
        def_pattern = re.compile(rf"^\s*(?:def|class|async\s+def)\s+{re.escape(name)}\b")
        out: list[IdeLocation] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in {".py", ".ts", ".js", ".go", ".rs"}:
                continue
            rel = path.relative_to(root).as_posix()
            text = path.read_text(encoding="utf-8")
            for i, row in enumerate(text.split("\n")):
                if definitions_only and not def_pattern.search(row):
                    continue
                for match in pattern.finditer(row):
                    out.append(
                        IdeLocation(
                            file_path=rel,
                            line=i,
                            character=match.start(),
                            end_line=i,
                            end_character=match.end(),
                        )
                    )
        return out
