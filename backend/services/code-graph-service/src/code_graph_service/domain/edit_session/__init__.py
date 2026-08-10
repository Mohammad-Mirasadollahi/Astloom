"""
Role: Session-scoped LSP edit intelligence (IDE-semantic refs/rename) for agents.
Source of truth / invariants: never writes durable CODE_REL; disk edits only under
root_path; converge via reconcile_after_edit → AST ingest (ADR 48 / feature 49).
Allowed failure: ValidationError / unavailable LS. Forbidden: cloud LS, path escape,
LSP dual-write into the graph store.
"""

from __future__ import annotations

from .fake import FakeEditSession
from .lsp_session import LspEditSession, build_default_edit_session
from .models import (
    IdeDefinitionResult,
    IdeLocation,
    IdeReferencesResult,
    IdeRenameResult,
)
from .protocol import EditSessionPort

__all__ = [
    "EditSessionPort",
    "FakeEditSession",
    "IdeDefinitionResult",
    "IdeLocation",
    "IdeReferencesResult",
    "IdeRenameResult",
    "LspEditSession",
    "build_default_edit_session",
]
