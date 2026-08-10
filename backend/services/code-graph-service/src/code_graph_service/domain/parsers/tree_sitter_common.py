"""Shared tree-sitter helpers for multi-language symbol extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tree_sitter import Language, Node, Parser


def build_parser(language: Any) -> Parser:
    return Parser(Language(language))


def node_text(source: bytes, node: Node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def first_child_named(node: Node, *types: str) -> Node | None:
    for child in node.children:
        if child.type in types:
            return child
    return None


def named_children(node: Node, *types: str) -> list[Node]:
    return [child for child in node.children if child.type in types]


def module_prefix_from_path(file_path: str, strip_suffixes: tuple[str, ...]) -> str:
    normalized = file_path.replace("\\", "/")
    path = Path(normalized)
    name = path.name
    for suffix in strip_suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    parts = list(path.parent.parts) + ([name] if name else [])
    parts = [part for part in parts if part not in {"", ".", ".."}]
    return ".".join(parts) if parts else "module"


def collect_calls(
    source: bytes,
    root: Node,
    call_types: frozenset[str] = frozenset({"call_expression"}),
) -> list[str]:
    names: set[str] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in call_types:
            callee = node.child_by_field_name("function")
            if callee is None and node.named_children:
                callee = node.named_children[0]
            if callee is not None:
                raw = _normalize_call_name(node_text(source, callee).strip())
                if raw:
                    names.add(raw)
        stack.extend(reversed(node.children))
    return sorted(names)


def _normalize_call_name(name: str) -> str:
    cleaned = name.replace(" ", "")
    if cleaned.startswith("self.") or cleaned.startswith("this.") or cleaned.startswith("Self::"):
        return cleaned.split(".", 1)[-1].split("::", 1)[-1]
    if "::" in cleaned:
        return cleaned.split("::")[-1]
    return cleaned
