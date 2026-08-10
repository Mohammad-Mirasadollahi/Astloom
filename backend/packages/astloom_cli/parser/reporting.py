"""``status``, ``inventory``, ``docs-standards``, ``stats``."""

from __future__ import annotations

import argparse

from astloom_cli.util import add_scope_args


def register_status(sub: argparse._SubParsersAction) -> None:
    status = sub.add_parser(
        "status",
        help="Show platform + graph sync status (one command)",
    )
    add_scope_args(status, required=False)
    status.add_argument("--json", action="store_true", help="Print full JSON only")
    status.add_argument("--verbose", action="store_true", help="Human summary + JSON")


def register(sub: argparse._SubParsersAction) -> None:
    register_status(sub)

    inventory = sub.add_parser(
        "inventory",
        help="List code/docs done vs remaining for pinned client software roots",
        epilog="Modes (no dashed flags): astloom inventory | astloom inventory detail | "
        "astloom inventory save <file> | astloom inventory detail save <file>",
    )
    inventory.add_argument(
        "words",
        nargs="*",
        help="Optional words: detail | save <path> | detail save <path>",
    )

    docs_standards = sub.add_parser(
        "docs-standards",
        help="Report which docs/ Markdown files fail Astloom documentation standards",
        epilog="Modes (no dashed flags): astloom docs-standards | astloom docs-standards detail | "
        "astloom docs-standards save <file> | astloom docs-standards detail save <file>",
    )
    docs_standards.add_argument(
        "words",
        nargs="*",
        help="Optional words: detail | save <path> | detail save <path>",
    )

    quality_audit = sub.add_parser(
        "quality-audit",
        help="Categorized quality audit for docs + code (standards, size, linking, sync gaps)",
        epilog="Modes (no dashed flags): astloom quality-audit | astloom quality-audit detail | "
        "astloom quality-audit save | astloom quality-audit save <file> | "
        "astloom quality-audit detail save [<file>]",
    )
    quality_audit.add_argument(
        "words",
        nargs="*",
        help="Optional words: detail | save [<path>] | detail save [<path>]",
    )

    docs_suggest = sub.add_parser(
        "docs-suggest-links",
        help="Hybrid evidence-only linked_symbols suggestions (path citations → tokens; no invented edges)",
    )
    docs_suggest.add_argument(
        "--path",
        default="",
        help="Single Markdown file (repo-relative or absolute); default: scan --docs-root",
    )
    docs_suggest.add_argument(
        "--docs-root",
        default="docs",
        help="Directory under repo root to scan when --path is omitted (default: docs)",
    )
    docs_suggest.add_argument(
        "--include-all",
        action="store_true",
        help="Include files with zero new suggestions (already linked / no evidence)",
    )
    docs_suggest.add_argument(
        "--apply",
        action="store_true",
        help="Write suggested tokens into frontmatter linked_symbols (still need astloom sync)",
    )
    docs_suggest.add_argument(
        "--json",
        action="store_true",
        help="Print JSON report",
    )

    docs_catalog = sub.add_parser(
        "docs-catalog",
        help="Cached docs frontmatter catalog (tags/lanes) for agent retrieval; no invented edges",
    )
    docs_catalog.add_argument(
        "--refresh",
        action="store_true",
        help="Rebuild .astloom/cache/docs-catalog.json from disk",
    )
    docs_catalog.add_argument(
        "--roots",
        default="",
        help="Comma-separated doc roots under repo (default: env ASTLOOM_DOCS_CATALOG_ROOTS or built-in defaults)",
    )
    docs_catalog.add_argument("--tag", default="", help="Filter by tag (case-insensitive)")
    docs_catalog.add_argument("--concern", default="", help="Filter by concern_lane")
    docs_catalog.add_argument("--lifecycle", default="", help="Filter by lifecycle_lane")
    docs_catalog.add_argument("--audience", default="", help="Filter by audience_lane value")
    docs_catalog.add_argument("--phase", default="", help="Filter by phase")
    docs_catalog.add_argument("--doc-type", default="", dest="doc_type", help="Filter by doc_type")
    docs_catalog.add_argument(
        "--query",
        default="",
        help="Substring match on path/title/summary/tags/doc_id",
    )
    docs_catalog.add_argument(
        "--linked-only",
        action="store_true",
        help="Only documents that already have linked_symbols",
    )
    docs_catalog.add_argument(
        "--unlinked-only",
        action="store_true",
        help="Only documents with empty linked_symbols",
    )
    docs_catalog.add_argument("--limit", type=int, default=50, help="Max matched documents (default 50)")
    docs_catalog.add_argument("--json", action="store_true", help="Print JSON report")

    stats = sub.add_parser(
        "stats",
        help="Count code/docs, language mix, and processed vs remaining percents",
        epilog="Modes (no dashed flags): astloom stats | astloom stats detail | "
        "astloom stats save <file> | astloom stats detail save <file>",
    )
    stats.add_argument(
        "words",
        nargs="*",
        help="Optional words: detail | save <path> | detail save <path>",
    )
