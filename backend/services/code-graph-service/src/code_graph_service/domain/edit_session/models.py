"""Edit-session result models (IDE-semantic; not durable graph edges)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..parsing_authority import SESSION_EDGE_REFERENCE_KIND


@dataclass(frozen=True)
class IdeLocation:
    file_path: str
    line: int
    character: int
    end_line: int | None = None
    end_character: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "file_path": self.file_path,
            "line": self.line,
            "character": self.character,
        }
        if self.end_line is not None:
            payload["end_line"] = self.end_line
        if self.end_character is not None:
            payload["end_character"] = self.end_character
        return payload


@dataclass
class IdeReferencesResult:
    available: bool
    reference_kind: str = SESSION_EDGE_REFERENCE_KIND
    locations: list[IdeLocation] = field(default_factory=list)
    language: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "reference_kind": self.reference_kind,
            "language": self.language,
            "detail": self.detail,
            "locations": [loc.to_dict() for loc in self.locations],
            "count": len(self.locations),
        }


@dataclass
class IdeDefinitionResult:
    available: bool
    reference_kind: str = SESSION_EDGE_REFERENCE_KIND
    locations: list[IdeLocation] = field(default_factory=list)
    language: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "reference_kind": self.reference_kind,
            "language": self.language,
            "detail": self.detail,
            "locations": [loc.to_dict() for loc in self.locations],
            "count": len(self.locations),
        }


@dataclass
class IdeRenameResult:
    available: bool
    applied: bool = False
    reference_kind: str = SESSION_EDGE_REFERENCE_KIND
    changed_files: list[str] = field(default_factory=list)
    language: str = ""
    detail: str = ""
    reconcile: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "applied": self.applied,
            "reference_kind": self.reference_kind,
            "language": self.language,
            "detail": self.detail,
            "changed_files": list(self.changed_files),
            "reconcile": dict(self.reconcile),
        }
