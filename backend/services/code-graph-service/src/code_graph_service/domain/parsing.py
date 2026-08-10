"""Python AST parsing and call-resolution helpers."""

from __future__ import annotations

import ast
import builtins
import keyword
import re

from .enums import CallConfidence, SymbolKind
from .hashing import digest
from .models import ParsedSymbol, ParseResult


def parse_python_source(file_path: str, source: str) -> ParseResult:
    tree = ast.parse(source)
    module = file_path.replace("\\", "/").removesuffix(".py").replace("/", ".")
    results: list[ParsedSymbol] = []
    import_aliases: dict[str, str] = {}

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names: list[str] = []
            aliases: dict[str, str] = {}
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.append(alias.name)
                    local = alias.asname or alias.name.split(".", 1)[0]
                    aliases[local] = alias.name
            else:
                root = node.module or ""
                for alias in node.names:
                    target = f"{root}.{alias.name}" if root else alias.name
                    names.append(target)
                    local = alias.asname or alias.name
                    aliases[local] = target
            import_aliases.update(aliases)
            text = ast.get_source_segment(source, node) or ""
            results.append(
                ParsedSymbol(
                    kind=SymbolKind.IMPORT,
                    name=names[0] if names else "import",
                    qualified_name=f"{module}::__import__::{digest(text)[:8]}",
                    signature=text.strip(),
                    body=text,
                    calls=[],
                    imports=names,
                    bases=[],
                    import_aliases=aliases,
                )
            )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            results.append(_function_symbol(module, source, node, SymbolKind.FUNCTION))
        elif isinstance(node, ast.ClassDef):
            class_q = f"{module}.{node.name}"
            class_body = ast.get_source_segment(source, node) or node.name
            bases = [_expr_name(base) for base in node.bases]
            results.append(
                ParsedSymbol(
                    kind=SymbolKind.CLASS,
                    name=node.name,
                    qualified_name=class_q,
                    signature=f"class {node.name}",
                    body=class_body,
                    calls=[],
                    imports=[],
                    bases=[b for b in bases if b],
                    visibility="private" if node.name.startswith("_") else "public",
                )
            )
            for child in node.body:
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    results.append(_function_symbol(class_q, source, child, SymbolKind.METHOD))
    return ParseResult(symbols=results, import_aliases=import_aliases, module_prefix=module)


def _function_symbol(
    owner: str,
    source: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    kind: SymbolKind,
) -> ParsedSymbol:
    body = ast.get_source_segment(source, node) or node.name
    args = [arg.arg for arg in node.args.args]
    signature = f"{node.name}({', '.join(args)})"
    direct_calls = {
        _normalize_call_name(_call_name(n))
        for n in ast.walk(node)
        if isinstance(n, ast.Call)
    }
    reflection = {
        _normalize_call_name(name) for name in _getattr_call_names(node)
    }
    # getattr itself is not a meaningful callee for CALLS densification.
    direct_calls.discard("getattr")
    calls = sorted(c for c in (direct_calls | reflection) if c)
    return ParsedSymbol(
        kind=kind,
        name=node.name,
        qualified_name=f"{owner}.{node.name}",
        signature=signature,
        body=body,
        calls=calls,
        imports=[],
        bases=[],
        visibility="private" if node.name.startswith("_") else "public",
        reflection_calls=sorted(c for c in reflection if c),
    )


def _getattr_call_names(node: ast.AST) -> set[str]:
    """Capture getattr(obj, 'method') as call refs for denser CALLS resolution (Wave D)."""
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Name) or child.func.id != "getattr":
            continue
        if len(child.args) < 2:
            continue
        attr = child.args[1]
        if isinstance(attr, ast.Constant) and isinstance(attr.value, str):
            names.add(attr.value)
    return names


def _expr_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _expr_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _call_name(node: ast.Call) -> str:
    return _expr_name(node.func)


def _normalize_call_name(name: str) -> str:
    if name.startswith("self.") or name.startswith("cls."):
        return name.split(".", 1)[1]
    return name


def extract_call_refs(source: str) -> set[str]:
    """Call-site names used for generated-code unknown-symbol checks."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", source))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        raw = _normalize_call_name(_call_name(node))
        if not raw:
            continue
        names.add(raw)
        names.add(raw.split(".")[-1])
    return names


def defined_names(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", 1)[0])
    return names


def builtin_names() -> set[str]:
    return set(dir(builtins)) | set(keyword.kwlist) | {"self", "cls"}


def resolve_call_target(
    call: str,
    *,
    by_qualified: dict[str, str],
    short_names: dict[str, list[str]],
    import_aliases: dict[str, str],
    module_prefix: str,
    source_language: str = "python",
) -> tuple[list[str], CallConfidence]:
    """Resolve call name to symbol id(s) with confidence."""
    if call in by_qualified:
        return [by_qualified[call]], CallConfidence.EXACT

    local_qualified = f"{module_prefix}.{call}" if module_prefix else call
    if local_qualified in by_qualified:
        return [by_qualified[local_qualified]], CallConfidence.EXACT

    if call in import_aliases:
        expanded = import_aliases[call]
        if expanded in by_qualified:
            return [by_qualified[expanded]], CallConfidence.PROBABLE
        short = expanded.split(".")[-1]
        matches = list(short_names.get(short, []))
        if len(matches) == 1:
            return matches, CallConfidence.PROBABLE
        if len(matches) > 1:
            return matches, CallConfidence.AMBIGUOUS

    if "." in call:
        head, tail = call.split(".", 1)
        if head in import_aliases:
            expanded = f"{import_aliases[head]}.{tail}"
            if expanded in by_qualified:
                return [by_qualified[expanded]], CallConfidence.PROBABLE
            short = short_names.get(tail, [])
            if len(short) == 1:
                return short, CallConfidence.PROBABLE
            if len(short) > 1:
                return short, CallConfidence.AMBIGUOUS

    if (
        source_language.strip().lower() == "python"
        and "." not in call
        and call in builtin_names()
    ):
        return [], CallConfidence.EXTERNAL

    short = call.split(".")[-1]
    matches = list(short_names.get(short, []))
    if not matches:
        return [], CallConfidence.UNRESOLVED
    if len(matches) == 1:
        return matches, CallConfidence.EXACT if "." not in call else CallConfidence.PROBABLE

    same_module = [
        mid
        for qname, mid in by_qualified.items()
        if mid in matches and qname.startswith(f"{module_prefix}.")
    ]
    if len(same_module) == 1:
        return same_module, CallConfidence.PROBABLE
    return matches, CallConfidence.AMBIGUOUS
