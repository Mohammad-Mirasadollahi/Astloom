"""Real subprocess LSP edit session (local language servers only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import ValidationError
from ..languages import detect_language_from_path
from .jsonrpc import JsonRpcLspClient
from .models import IdeDefinitionResult, IdeLocation, IdeReferencesResult, IdeRenameResult
from .servers import lsp_edit_session_enabled, normalize_edit_language, resolve_language_server
from .workspace_edit import apply_workspace_edit, file_uri, resolve_under_root


class LspEditSession:
    """IDE-semantic session backed by a local language server over stdio."""

    def __init__(self, client: JsonRpcLspClient, *, language: str, root: Path) -> None:
        self._client = client
        self._language = language
        self._root = root
        self._opened: set[str] = set()

    def close(self) -> None:
        try:
            self._client.notify("exit", {})
        except Exception:  # noqa: BLE001
            pass
        self._client.close()

    def find_references(
        self,
        *,
        root_path: str,
        file_path: str,
        line: int,
        character: int,
        language: str = "",
    ) -> IdeReferencesResult:
        rel, abs_path, lang = self._prepare(root_path, file_path, language)
        self._ensure_open(rel, abs_path)
        result = self._client.request(
            "textDocument/references",
            {
                "textDocument": {"uri": file_uri(abs_path)},
                "position": {"line": int(line), "character": int(character)},
                "context": {"includeDeclaration": True},
            },
        )
        return IdeReferencesResult(
            available=True,
            language=lang,
            locations=_locations_from_lsp(result, self._root),
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
        rel, abs_path, lang = self._prepare(root_path, file_path, language)
        self._ensure_open(rel, abs_path)
        result = self._client.request(
            "textDocument/definition",
            {
                "textDocument": {"uri": file_uri(abs_path)},
                "position": {"line": int(line), "character": int(character)},
            },
        )
        return IdeDefinitionResult(
            available=True,
            language=lang,
            locations=_locations_from_lsp(result, self._root),
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
        name = (new_name or "").strip()
        if not name:
            raise ValidationError("new_name is required")
        rel, abs_path, lang = self._prepare(root_path, file_path, language)
        self._ensure_open(rel, abs_path)
        workspace_edit = self._client.request(
            "textDocument/rename",
            {
                "textDocument": {"uri": file_uri(abs_path)},
                "position": {"line": int(line), "character": int(character)},
                "newName": name,
            },
        )
        if not workspace_edit:
            return IdeRenameResult(
                available=True,
                applied=False,
                language=lang,
                detail="language server returned no WorkspaceEdit",
            )
        if not apply:
            return IdeRenameResult(
                available=True,
                applied=False,
                language=lang,
                detail="apply=false; WorkspaceEdit not written",
                changed_files=[],
            )
        changed = apply_workspace_edit(str(self._root), dict(workspace_edit))
        return IdeRenameResult(
            available=True,
            applied=True,
            language=lang,
            changed_files=changed,
            detail="workspace edit applied; caller must reconcile_after_edit",
        )

    def _prepare(self, root_path: str, file_path: str, language: str) -> tuple[str, Path, str]:
        rel, abs_path = resolve_under_root(root_path, file_path)
        if abs_path.resolve() != self._root.resolve() and not str(abs_path).startswith(str(self._root)):
            # root must match session root
            if Path(root_path).resolve() != self._root:
                raise ValidationError("root_path does not match edit session root")
        lang = normalize_edit_language(
            language or detect_language_from_path(rel) or self._language,
            rel,
        )
        return rel, abs_path, lang

    def _ensure_open(self, rel: str, abs_path: Path) -> None:
        if rel in self._opened:
            return
        if not abs_path.is_file():
            raise ValidationError(f"file not found: {rel}")
        text = abs_path.read_text(encoding="utf-8")
        language_id = {
            "python": "python",
            "typescript": "typescript",
            "javascript": "javascript",
            "go": "go",
            "rust": "rust",
        }.get(self._language, self._language)
        self._client.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": file_uri(abs_path),
                    "languageId": language_id,
                    "version": 1,
                    "text": text,
                }
            },
        )
        self._opened.add(rel)


def build_default_edit_session(
    *,
    root_path: str,
    language: str = "",
    file_path: str = "",
) -> LspEditSession | None:
    """Create a live LS session when enabled and a local binary exists."""
    if not lsp_edit_session_enabled():
        return None
    root = Path(root_path).expanduser().resolve()
    if not root.is_dir():
        raise ValidationError(f"root_path is not a directory: {root}")
    spec = resolve_language_server(language, file_path)
    if spec is None:
        return None
    client = JsonRpcLspClient(spec.argv, cwd=str(root))
    try:
        client.request(
            "initialize",
            {
                "processId": None,
                "rootUri": file_uri(root),
                "capabilities": {
                    "textDocument": {
                        "references": {"dynamicRegistration": False},
                        "definition": {"dynamicRegistration": False},
                        "rename": {"prepareSupport": False},
                    }
                },
                "workspaceFolders": [{"uri": file_uri(root), "name": root.name}],
            },
        )
        client.notify("initialized", {})
    except Exception:
        client.close()
        raise
    return LspEditSession(client, language=spec.language, root=root)


def _locations_from_lsp(result: Any, root: Path) -> list[IdeLocation]:
    items: list[Any]
    if result is None:
        items = []
    elif isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        items = [result]
    else:
        items = []
    out: list[IdeLocation] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        target = item.get("targetUri") or item.get("uri")
        rng = item.get("targetSelectionRange") or item.get("targetRange") or item.get("range") or {}
        start = rng.get("start") or {}
        end = rng.get("end") or {}
        if not target:
            continue
        from .workspace_edit import uri_to_path

        path = uri_to_path(str(target), root)
        try:
            rel = path.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = str(path)
        out.append(
            IdeLocation(
                file_path=rel,
                line=int(start.get("line") or 0),
                character=int(start.get("character") or 0),
                end_line=int(end.get("line") or 0) if end else None,
                end_character=int(end.get("character") or 0) if end else None,
            )
        )
    return out
