"""Classify calls that resolve outside the repository (high-confidence only)."""

from __future__ import annotations

from .confidence_policy import impact_eligible
from .enums import CallConfidence
from .parsing import builtin_names

# Only well-known stdlib module roots. Conservative on purpose: prefer
# ``unresolved`` over false ``external`` for project / third-party ambiguity.
_STDLIB_ROOTS = frozenset(
    {
        "abc",
        "argparse",
        "ast",
        "asyncio",
        "base64",
        "builtins",
        "collections",
        "contextlib",
        "copy",
        "csv",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "functools",
        "hashlib",
        "http",
        "importlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "os",
        "pathlib",
        "pickle",
        "platform",
        "re",
        "shutil",
        "signal",
        "socket",
        "sqlite3",
        "ssl",
        "statistics",
        "string",
        "struct",
        "subprocess",
        "sys",
        "tempfile",
        "textwrap",
        "threading",
        "time",
        "traceback",
        "typing",
        "uuid",
        "urllib",
        "warnings",
        "weakref",
        "xml",
        "zipfile",
        "zlib",
    }
)


def external_call_symbol_id(project_id: str, call: str) -> str:
    """Stable placeholder id for an out-of-repo call target."""
    return f"ext:call:{project_id}:{call}"


def is_external_call_id(symbol_id: str) -> bool:
    return str(symbol_id).startswith("ext:call:")


def is_project_symbol_id(symbol_id: str) -> bool:
    """Project code symbols use ``sym:{project}:{qualified}`` ids."""
    return str(symbol_id).startswith("sym:")


def _stdlib_root(name: str) -> bool:
    root = str(name or "").strip().split(".", 1)[0]
    return bool(root) and root in _STDLIB_ROOTS


def classify_external_call(
    call: str,
    *,
    import_aliases: dict[str, str] | None = None,
) -> str | None:
    """Return an external kind only when confidence is high.

    Used only after project resolution failed. Labels:
    ``builtin``, ``stdlib``, ``imported_external``.

    Deliberately does **not** tag bare methods (``strip``) or
    ``receiver.method`` on locals — those stay ``unresolved`` to avoid
    false externals for project helpers with common names.
    """
    name = str(call or "").strip()
    if not name:
        return None

    builtins = builtin_names()
    if name in builtins:
        return "builtin"

    if _stdlib_root(name):
        return "stdlib"

    aliases = import_aliases or {}
    head, _, _tail = name.partition(".")
    expanded = aliases.get(name) or aliases.get(head)
    if expanded and _stdlib_root(expanded):
        return "imported_external"

    return None


def is_blast_call_edge(
    *,
    target_id: str,
    metadata: dict | None = None,
    confidence: CallConfidence | str | None = None,
) -> bool:
    """Whether a CALLS edge should participate in blast / flow / explore expansion.

    Only edges to project ``sym:`` targets count. Tagged externals, import stubs,
    and unresolved placeholders are excluded from blast radius.
    """
    if metadata and metadata.get("is_external"):
        return False
    if not is_project_symbol_id(target_id):
        return False
    return confidence is None or impact_eligible(confidence)
