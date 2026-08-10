"""TypeScript / TSX tree-sitter parser."""

from __future__ import annotations

from ..enums import SymbolKind
from ..models import ParsedSymbol, ParseResult
from .javascript import (
    _class_symbols,
    _function_symbol,
    _import_symbol,
    _top_level_declaration,
)
from .tree_sitter_common import build_parser, first_child_named, module_prefix_from_path, node_text


def parse_typescript_source(file_path: str, source: str) -> ParseResult:
    import tree_sitter_typescript as ts_ts

    use_tsx = file_path.endswith((".tsx", ".jsx"))
    language_capsule = ts_ts.language_tsx() if use_tsx else ts_ts.language_typescript()
    parser = build_parser(language_capsule)
    source_bytes = source.encode("utf-8")
    root = parser.parse(source_bytes).root_node
    module = module_prefix_from_path(file_path, (".tsx", ".ts", ".mts", ".cts"))
    symbols: list[ParsedSymbol] = []
    import_aliases: dict[str, str] = {}

    for node in root.named_children:
        if node.type == "import_statement":
            symbols.append(_import_symbol(source_bytes, module, node, import_aliases))
        elif node.type == "export_statement":
            declaration = first_child_named(
                node,
                "function_declaration",
                "class_declaration",
                "lexical_declaration",
                "interface_declaration",
                "type_alias_declaration",
            )
            if declaration is not None:
                symbols.extend(_ts_declaration(source_bytes, module, declaration, import_aliases))
        else:
            symbols.extend(_ts_declaration(source_bytes, module, node, import_aliases))

    return ParseResult(symbols=symbols, import_aliases=import_aliases, module_prefix=module)


def _ts_declaration(
    source: bytes,
    module: str,
    node,
    import_aliases: dict[str, str],
) -> list[ParsedSymbol]:
    if node.type in {"interface_declaration", "type_alias_declaration"}:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return []
        name = node_text(source, name_node)
        body = node_text(source, node)
        return [
            ParsedSymbol(
                kind=SymbolKind.CLASS,
                name=name,
                qualified_name=f"{module}.{name}",
                signature=f"{'interface' if node.type == 'interface_declaration' else 'type'} {name}",
                body=body,
                calls=[],
                imports=[],
                bases=[],
                visibility="public",
            )
        ]
    if node.type == "function_declaration":
        return [_function_symbol(source, module, node, SymbolKind.FUNCTION)]
    if node.type == "class_declaration":
        return _class_symbols(source, module, node)
    return _top_level_declaration(source, module, node, import_aliases)
