"""Resolve frontmatter linked_symbols tokens to code-graph symbol ids."""

from __future__ import annotations

from .enums import SymbolKind
from .errors import NotFoundError
from .models import GraphSymbol, Scope
from .ports import Store


_SKIP_KINDS = frozenset(
    {
        SymbolKind.FILE,
        SymbolKind.DOCUMENTATION,
        SymbolKind.UNRESOLVED,
        SymbolKind.EXTERNAL,
        SymbolKind.IMPORT,
        SymbolKind.RATIONALE,
        SymbolKind.ROUTE,
    }
)


def resolve_linked_symbol(store: Store, scope: Scope, token: str) -> GraphSymbol | None:
    """Resolve a ``linked_symbols`` entry to a code symbol, or None if unresolved.

    Accepted forms:
    - exact ``qualified_name`` (e.g. ``auth.login`` or ``pkg.mod.fn``)
    - ``file_path::SymbolName`` (wiki style)
    """
    raw = str(token or "").strip()
    if not raw:
        return None

    if "::" in raw:
        file_path, _, name = raw.partition("::")
        file_path = file_path.strip().replace("\\", "/")
        name = name.strip()
        if not file_path or not name:
            return None
        for symbol in store.list_symbols_for_file(scope, file_path):
            if symbol.kind in _SKIP_KINDS:
                continue
            if symbol.name == name or symbol.qualified_name.endswith(f".{name}"):
                return symbol
        return None

    hit = store.get_symbol_by_qualified_name(scope, raw)
    if hit is not None and hit.kind not in _SKIP_KINDS:
        return hit
    # Also accept bare symbol id.
    try:
        by_id = store.get_symbol(raw, scope)
    except NotFoundError:
        by_id = None
    if by_id is not None and by_id.kind not in _SKIP_KINDS:
        return by_id
    return None
