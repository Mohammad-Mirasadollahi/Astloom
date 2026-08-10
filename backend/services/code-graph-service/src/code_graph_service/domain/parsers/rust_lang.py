"""Rust tree-sitter parser."""

from __future__ import annotations

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


def parse_rust_source(file_path: str, source: str) -> ParseResult:
    import tree_sitter_rust as ts_rust

    parser = build_parser(ts_rust.language())
    source_bytes = source.encode("utf-8")
    root = parser.parse(source_bytes).root_node
    module = module_prefix_from_path(file_path, (".rs",))
    symbols: list[ParsedSymbol] = []
    import_aliases: dict[str, str] = {}

    for node in root.named_children:
        symbols.extend(_item_symbols(source_bytes, module, node, import_aliases))

    return ParseResult(symbols=symbols, import_aliases=import_aliases, module_prefix=module)


def _item_symbols(
    source: bytes,
    module: str,
    node,
    import_aliases: dict[str, str],
) -> list[ParsedSymbol]:
    if node.type == "use_declaration":
        return [_use_symbol(source, module, node, import_aliases)]
    if node.type == "function_item":
        return [_function_symbol(source, module, node, SymbolKind.FUNCTION)]
    if node.type in {"struct_item", "enum_item", "trait_item", "type_item"}:
        return [_type_symbol(source, module, node)]
    if node.type == "impl_item":
        return _impl_symbols(source, module, node)
    if node.type == "mod_item":
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return []
        name = node_text(source, name_node)
        nested_module = f"{module}::{name}"
        body = node.child_by_field_name("body")
        results = [
            ParsedSymbol(
                kind=SymbolKind.CLASS,
                name=name,
                qualified_name=f"{module}.{name}",
                signature=f"mod {name}",
                body=node_text(source, node),
                calls=[],
                imports=[],
                bases=[],
                visibility=_rust_visibility(node, name),
            )
        ]
        if body is not None:
            for child in body.named_children:
                results.extend(_item_symbols(source, nested_module.replace("::", "."), child, import_aliases))
        return results
    return []


def _use_symbol(
    source: bytes,
    module: str,
    node,
    import_aliases: dict[str, str],
) -> ParsedSymbol:
    text = node_text(source, node).strip()
    argument = node.child_by_field_name("argument")
    path = node_text(source, argument).strip() if argument is not None else text
    local = path.split(" as ")[-1].strip().split("::")[-1].rstrip(";")
    target = path.split(" as ")[0].strip().rstrip(";")
    aliases = {local: target} if local else {}
    import_aliases.update(aliases)
    return ParsedSymbol(
        kind=SymbolKind.IMPORT,
        name=target or "use",
        qualified_name=f"{module}::__import__::{digest(text)[:8]}",
        signature=text,
        body=text,
        calls=[],
        imports=[target] if target else [],
        bases=[],
        import_aliases=aliases,
    )


def _function_symbol(source: bytes, owner: str, node, kind: SymbolKind) -> ParsedSymbol:
    name_node = node.child_by_field_name("name")
    name = node_text(source, name_node) if name_node is not None else "fn"
    params = node.child_by_field_name("parameters")
    param_text = node_text(source, params) if params is not None else "()"
    body = node_text(source, node)
    return ParsedSymbol(
        kind=kind,
        name=name,
        qualified_name=f"{owner}.{name}",
        signature=f"fn {name}{param_text}",
        body=body,
        calls=collect_calls(source, node, call_types=frozenset({"call_expression", "macro_invocation"})),
        imports=[],
        bases=[],
        visibility=_rust_visibility(node, name),
    )


def _type_symbol(source: bytes, module: str, node) -> ParsedSymbol:
    name_node = node.child_by_field_name("name")
    name = node_text(source, name_node) if name_node is not None else "Type"
    bases: list[str] = []
    if node.type == "trait_item":
        for child in named_children(node, "trait_bounds", "bounds"):
            bases.append(node_text(source, child))
    return ParsedSymbol(
        kind=SymbolKind.CLASS,
        name=name,
        qualified_name=f"{module}.{name}",
        signature=f"{node.type.replace('_item', '')} {name}",
        body=node_text(source, node),
        calls=[],
        imports=[],
        bases=bases,
        visibility=_rust_visibility(node, name),
    )


def _impl_symbols(source: bytes, module: str, node) -> list[ParsedSymbol]:
    type_node = node.child_by_field_name("type")
    trait_node = node.child_by_field_name("trait")
    type_name = node_text(source, type_node).strip() if type_node is not None else "Impl"
    owner = f"{module}.{type_name}"
    bases = [node_text(source, trait_node).strip()] if trait_node is not None else []
    results = [
        ParsedSymbol(
            kind=SymbolKind.CLASS,
            name=type_name,
            qualified_name=owner,
            signature=f"impl {type_name}",
            body=node_text(source, node),
            calls=[],
            imports=[],
            bases=bases,
            visibility="public",
        )
    ]
    body = node.child_by_field_name("body")
    if body is None:
        return results
    for child in body.named_children:
        if child.type == "function_item":
            results.append(_function_symbol(source, owner, child, SymbolKind.METHOD))
    return results


def _rust_visibility(node, name: str) -> str:
    if first_child_named(node, "visibility_modifier") is not None:
        return "public"
    return "private" if not name.startswith("pub") else "public"
