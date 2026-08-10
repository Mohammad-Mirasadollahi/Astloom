"""Live-until-proven path heuristics and blocker tags."""

from __future__ import annotations

from ..enums import SymbolKind
from ..flows import FlowNode, is_entry_point
from ..models import GraphSymbol
from .constants import PUBLIC_HTTP_HINT, STRING_REGISTRY_HINT, TSOC_DEFER
from .liveness import is_test_path


def blockers_for(symbol: GraphSymbol, *, inbound_any: int) -> list[str]:
    blockers: list[str] = []
    blob = f"{symbol.signature}\n{symbol.body[:800]}"
    node = FlowNode(
        id=symbol.id,
        name=symbol.name,
        qualified_name=symbol.qualified_name,
        file_path=symbol.file_path,
        signature=symbol.signature,
        body=symbol.body,
    )
    if is_entry_point(node, inbound_call_count=inbound_any, is_route_handler=False):
        blockers.append("entrypoint")
    if PUBLIC_HTTP_HINT.search(blob):
        blockers.append("public_http_handler")
    if STRING_REGISTRY_HINT.search(blob) or "__getattr__" in blob:
        blockers.append("possible_string_registry")
    if TSOC_DEFER.search(blob):
        blockers.append("tsoc_defer")
    if symbol.kind == SymbolKind.EXTERNAL:
        blockers.append("external_symbol")
    if is_test_path(symbol.file_path):
        blockers.append("tests_only_path")
    return blockers
