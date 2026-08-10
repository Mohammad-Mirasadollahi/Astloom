"""Go tree-sitter parser."""

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


def parse_go_source(file_path: str, source: str) -> ParseResult:
    import tree_sitter_go as ts_go

    parser = build_parser(ts_go.language())
    source_bytes = source.encode("utf-8")
    root = parser.parse(source_bytes).root_node
    module = module_prefix_from_path(file_path, (".go",))
    package_name = module
    symbols: list[ParsedSymbol] = []
    import_aliases: dict[str, str] = {}

    for node in root.named_children:
        if node.type == "package_clause":
            name_node = first_child_named(node, "package_identifier")
            if name_node is not None:
                package_name = node_text(source_bytes, name_node)
                module = package_name
        elif node.type == "import_declaration":
            symbols.extend(_import_symbols(source_bytes, module, node, import_aliases))
        elif node.type == "function_declaration":
            symbols.append(_function_symbol(source_bytes, module, node, receiver=None))
        elif node.type == "method_declaration":
            receiver = node.child_by_field_name("receiver")
            owner = module
            if receiver is not None:
                type_name = _receiver_type_name(source_bytes, receiver)
                if type_name:
                    owner = f"{module}.{type_name}"
            symbols.append(_function_symbol(source_bytes, owner, node, receiver=receiver))
        elif node.type == "type_declaration":
            symbols.extend(_type_symbols(source_bytes, module, node))

    return ParseResult(symbols=symbols, import_aliases=import_aliases, module_prefix=module)


def _receiver_type_name(source: bytes, receiver) -> str:
    stack = list(receiver.named_children)
    while stack:
        node = stack.pop()
        if node.type == "type_identifier":
            return node_text(source, node)
        stack.extend(node.named_children)
    return ""


def _import_symbols(
    source: bytes,
    module: str,
    node,
    import_aliases: dict[str, str],
) -> list[ParsedSymbol]:
    results: list[ParsedSymbol] = []
    specs = named_children(node, "import_spec", "import_spec_list")
    targets: list[tuple[str, str]] = []
    for spec in specs:
        if spec.type == "import_spec_list":
            for inner in named_children(spec, "import_spec"):
                targets.append(_import_spec(source, inner))
        else:
            targets.append(_import_spec(source, spec))
    for local, path in targets:
        if not path:
            continue
        aliases = {local: path} if local else {}
        import_aliases.update(aliases)
        text = f'import {local + " " if local else ""}"{path}"'.strip()
        results.append(
            ParsedSymbol(
                kind=SymbolKind.IMPORT,
                name=path,
                qualified_name=f"{module}::__import__::{digest(text)[:8]}",
                signature=text,
                body=text,
                calls=[],
                imports=[path],
                bases=[],
                import_aliases=aliases,
            )
        )
    return results


def _import_spec(source: bytes, node) -> tuple[str, str]:
    name_node = node.child_by_field_name("name")
    path_node = node.child_by_field_name("path")
    path = node_text(source, path_node).strip('"') if path_node is not None else ""
    local = node_text(source, name_node) if name_node is not None else path.rsplit("/", 1)[-1]
    return local, path


def _function_symbol(source: bytes, owner: str, node, *, receiver) -> ParsedSymbol:
    name_node = node.child_by_field_name("name")
    name = node_text(source, name_node) if name_node is not None else "func"
    params = node.child_by_field_name("parameters")
    param_text = node_text(source, params) if params is not None else "()"
    body = node_text(source, node)
    kind = SymbolKind.METHOD if receiver is not None else SymbolKind.FUNCTION
    return ParsedSymbol(
        kind=kind,
        name=name,
        qualified_name=f"{owner}.{name}",
        signature=f"func {name}{param_text}",
        body=body,
        calls=collect_calls(source, node),
        imports=[],
        bases=[],
        visibility="private" if name[:1].islower() else "public",
    )


def _type_symbols(source: bytes, module: str, node) -> list[ParsedSymbol]:
    results: list[ParsedSymbol] = []
    for spec in named_children(node, "type_spec"):
        name_node = spec.child_by_field_name("name")
        type_node = spec.child_by_field_name("type")
        if name_node is None:
            continue
        name = node_text(source, name_node)
        body = node_text(source, spec)
        kind = SymbolKind.CLASS
        bases: list[str] = []
        if type_node is not None and type_node.type == "interface_type":
            for child in type_node.named_children:
                if child.type == "type_identifier":
                    bases.append(node_text(source, child))
        results.append(
            ParsedSymbol(
                kind=kind,
                name=name,
                qualified_name=f"{module}.{name}",
                signature=f"type {name}",
                body=body,
                calls=[],
                imports=[],
                bases=bases,
                visibility="private" if name[:1].islower() else "public",
            )
        )
    return results
