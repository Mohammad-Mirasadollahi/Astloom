"""JavaScript / JSX tree-sitter parser."""

from __future__ import annotations

from tree_sitter import Node

from ..enums import SymbolKind
from ..hashing import digest
from ..models import ParsedSymbol, ParseResult
from .tree_sitter_common import (
    build_parser,
    collect_calls,
    first_child_named,
    module_prefix_from_path,
    named_children,
    node_text,
)


def parse_javascript_source(file_path: str, source: str) -> ParseResult:
    import tree_sitter_javascript as ts_js

    parser = build_parser(ts_js.language())
    source_bytes = source.encode("utf-8")
    root = parser.parse(source_bytes).root_node
    module = module_prefix_from_path(file_path, (".jsx", ".js", ".mjs", ".cjs"))
    symbols: list[ParsedSymbol] = []
    import_aliases: dict[str, str] = {}

    for node in root.named_children:
        if node.type == "import_statement":
            symbols.append(_import_symbol(source_bytes, module, node, import_aliases))
        elif node.type == "export_statement":
            declaration = first_child_named(
                node, "function_declaration", "class_declaration", "lexical_declaration"
            )
            if declaration is not None:
                symbols.extend(
                    _top_level_declaration(source_bytes, module, declaration, import_aliases)
                )
        else:
            symbols.extend(_top_level_declaration(source_bytes, module, node, import_aliases))

    return ParseResult(symbols=symbols, import_aliases=import_aliases, module_prefix=module)


def _top_level_declaration(
    source: bytes,
    module: str,
    node,
    import_aliases: dict[str, str],
) -> list[ParsedSymbol]:
    if node.type == "function_declaration":
        return [_function_symbol(source, module, node, SymbolKind.FUNCTION)]
    if node.type == "class_declaration":
        return _class_symbols(source, module, node)
    if node.type == "lexical_declaration":
        # const foo = () => {}
        results: list[ParsedSymbol] = []
        for declarator in named_children(node, "variable_declarator"):
            name_node = declarator.child_by_field_name("name")
            value = declarator.child_by_field_name("value")
            if name_node is None or value is None:
                continue
            if value.type not in {"arrow_function", "function_expression", "function"}:
                continue
            name = node_text(source, name_node)
            body = node_text(source, declarator)
            results.append(
                ParsedSymbol(
                    kind=SymbolKind.FUNCTION,
                    name=name,
                    qualified_name=f"{module}.{name}",
                    signature=f"{name}()",
                    body=body,
                    calls=collect_calls(source, value),
                    imports=[],
                    bases=[],
                    visibility="private" if name.startswith("_") else "public",
                )
            )
        return results
    return []


def _class_symbols(source: bytes, module: str, node) -> list[ParsedSymbol]:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return []
    name = node_text(source, name_node)
    class_q = f"{module}.{name}"
    heritage = node.child_by_field_name("heritage") or first_child_named(node, "class_heritage")
    bases: list[str] = []
    if heritage is not None:
        for child in heritage.named_children:
            bases.append(node_text(source, child).strip())
    body = node_text(source, node)
    results = [
        ParsedSymbol(
            kind=SymbolKind.CLASS,
            name=name,
            qualified_name=class_q,
            signature=f"class {name}",
            body=body,
            calls=[],
            imports=[],
            bases=[b for b in bases if b],
            visibility="private" if name.startswith("_") else "public",
        )
    ]
    class_body = node.child_by_field_name("body")
    if class_body is None:
        return results
    for child in class_body.named_children:
        if child.type == "method_definition":
            results.append(_method_symbol(source, class_q, child))
    return results


def _method_symbol(source: bytes, owner: str, node) -> ParsedSymbol:
    name_node = node.child_by_field_name("name")
    name = node_text(source, name_node) if name_node is not None else "method"
    params = node.child_by_field_name("parameters")
    param_text = node_text(source, params) if params is not None else "()"
    body = node_text(source, node)
    return ParsedSymbol(
        kind=SymbolKind.METHOD,
        name=name,
        qualified_name=f"{owner}.{name}",
        signature=f"{name}{param_text}",
        body=body,
        calls=collect_calls(source, node),
        imports=[],
        bases=[],
        visibility="private" if name.startswith("_") else "public",
    )


def _function_symbol(source: bytes, owner: str, node, kind: SymbolKind) -> ParsedSymbol:
    name_node = node.child_by_field_name("name")
    name = node_text(source, name_node) if name_node is not None else "anonymous"
    params = node.child_by_field_name("parameters")
    param_text = node_text(source, params) if params is not None else "()"
    body = node_text(source, node)
    return ParsedSymbol(
        kind=kind,
        name=name,
        qualified_name=f"{owner}.{name}",
        signature=f"{name}{param_text}",
        body=body,
        calls=collect_calls(source, node),
        imports=[],
        bases=[],
        visibility="private" if name.startswith("_") else "public",
    )


def _import_symbol(
    source: bytes,
    module: str,
    node,
    import_aliases: dict[str, str],
) -> ParsedSymbol:
    text = node_text(source, node).strip()
    names: list[str] = []
    aliases: dict[str, str] = {}
    source_node = node.child_by_field_name("source")
    module_path = node_text(source, source_node).strip("\"'") if source_node is not None else ""
    for child in node.named_children:
        if child.type == "import_clause":
            for part in child.named_children:
                if part.type == "identifier":
                    local = node_text(source, part)
                    target = module_path or local
                    names.append(target)
                    aliases[local] = target
                elif part.type == "named_imports":
                    for spec in named_children(part, "import_specifier"):
                        imported = spec.child_by_field_name("name")
                        local_node = spec.child_by_field_name("alias") or imported
                        if imported is None or local_node is None:
                            continue
                        imported_name = node_text(source, imported)
                        local = node_text(source, local_node)
                        target = f"{module_path}.{imported_name}" if module_path else imported_name
                        names.append(target)
                        aliases[local] = target
    import_aliases.update(aliases)
    return ParsedSymbol(
        kind=SymbolKind.IMPORT,
        name=names[0] if names else "import",
        qualified_name=f"{module}::__import__::{digest(text)[:8]}",
        signature=text,
        body=text,
        calls=[],
        imports=names,
        bases=[],
        import_aliases=aliases,
    )
