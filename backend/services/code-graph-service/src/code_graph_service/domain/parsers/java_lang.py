"""Java tree-sitter parser."""

from __future__ import annotations

from ..enums import SymbolKind
from ..hashing import digest
from ..models import ParsedSymbol, ParseResult
from .tree_sitter_common import (
    build_parser,
    collect_calls,
    module_prefix_from_path,
    named_children,
    node_text,
)

_JAVA_CALL_TYPES = frozenset({"method_invocation", "object_creation_expression"})


def parse_java_source(file_path: str, source: str) -> ParseResult:
    import tree_sitter_java as ts_java

    parser = build_parser(ts_java.language())
    source_bytes = source.encode("utf-8")
    root = parser.parse(source_bytes).root_node
    module = module_prefix_from_path(file_path, (".java",))
    symbols: list[ParsedSymbol] = []
    import_aliases: dict[str, str] = {}

    for node in root.named_children:
        if node.type == "package_declaration":
            pkg = _package_name(source_bytes, node)
            if pkg:
                module = pkg
        elif node.type == "import_declaration":
            symbols.append(_import_symbol(source_bytes, module, node, import_aliases))
        elif node.type in {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration"}:
            symbols.extend(_type_symbols(source_bytes, module, node))

    return ParseResult(symbols=symbols, import_aliases=import_aliases, module_prefix=module)


def _package_name(source: bytes, node) -> str:
    for child in node.named_children:
        if child.type in {"scoped_identifier", "identifier"}:
            return node_text(source, child)
    return ""


def _import_symbol(source: bytes, module: str, node, import_aliases: dict[str, str]) -> ParsedSymbol:
    path = ""
    for child in node.named_children:
        if child.type in {"scoped_identifier", "identifier"}:
            path = node_text(source, child)
    local = path.rsplit(".", 1)[-1] if path else "import"
    if local and path:
        import_aliases[local] = path
    text = node_text(source, node).strip()
    return ParsedSymbol(
        kind=SymbolKind.IMPORT,
        name=path or local,
        qualified_name=f"{module}::__import__::{digest(text)[:8]}",
        signature=text,
        body=text,
        calls=[],
        imports=[path] if path else [],
        bases=[],
        import_aliases={local: path} if local and path else {},
    )


def _type_symbols(source: bytes, module: str, node) -> list[ParsedSymbol]:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        for child in node.named_children:
            if child.type == "identifier":
                name_node = child
                break
    if name_node is None:
        return []
    name = node_text(source, name_node)
    owner = f"{module}.{name}"
    body = node_text(source, node)
    results = [
        ParsedSymbol(
            kind=SymbolKind.CLASS,
            name=name,
            qualified_name=owner,
            signature=f"{node.type.replace('_declaration', '')} {name}",
            body=body,
            calls=[],
            imports=[],
            bases=_super_types(source, node),
        )
    ]
    body_node = node.child_by_field_name("body")
    if body_node is None:
        for child in node.named_children:
            if child.type.endswith("_body"):
                body_node = child
                break
    if body_node is None:
        return results
    for child in body_node.named_children:
        if child.type == "method_declaration":
            results.append(_method_symbol(source, owner, child, SymbolKind.METHOD))
        elif child.type == "constructor_declaration":
            results.append(_method_symbol(source, owner, child, SymbolKind.METHOD))
        elif child.type in {"class_declaration", "interface_declaration", "enum_declaration"}:
            results.extend(_type_symbols(source, owner, child))
    return results


def _super_types(source: bytes, node) -> list[str]:
    bases: list[str] = []
    for child in node.named_children:
        if child.type in {"superclass", "super_interfaces", "extends_interfaces"}:
            for leaf in child.named_children:
                if leaf.type in {"type_identifier", "scoped_type_identifier", "generic_type"}:
                    bases.append(node_text(source, leaf).split("<", 1)[0].strip())
    return bases


def _method_symbol(source: bytes, owner: str, node, kind: SymbolKind) -> ParsedSymbol:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        for child in named_children(node, "identifier"):
            name_node = child
            break
    name = node_text(source, name_node) if name_node is not None else "method"
    params = node.child_by_field_name("parameters")
    param_text = node_text(source, params) if params is not None else "()"
    body = node_text(source, node)
    calls = collect_calls(source, node, call_types=_JAVA_CALL_TYPES)
    return ParsedSymbol(
        kind=kind,
        name=name,
        qualified_name=f"{owner}.{name}",
        signature=f"{name}{param_text}",
        body=body,
        calls=calls,
        imports=[],
        bases=[],
    )
