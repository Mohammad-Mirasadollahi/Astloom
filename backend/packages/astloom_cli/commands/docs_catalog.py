"""``astloom docs-catalog`` — cached docs frontmatter index for agent retrieval."""

from __future__ import annotations

import argparse
import json

from astloom_cli import ui
from astloom_cli.docs_catalog import filter_docs_catalog, get_docs_catalog
from astloom_cli.util import repo_root


def cmd_docs_catalog(args: argparse.Namespace) -> int:
    root = repo_root().resolve()
    refresh = bool(getattr(args, "refresh", False))
    as_json = bool(getattr(args, "json", False))
    roots_arg = str(getattr(args, "roots", "") or "").strip()
    roots = [p.strip() for p in roots_arg.split(",") if p.strip()] if roots_arg else None
    has_links = None
    if bool(getattr(args, "linked_only", False)):
        has_links = True
    elif bool(getattr(args, "unlinked_only", False)):
        has_links = False

    catalog = get_docs_catalog(root, refresh=refresh or bool(roots), roots=roots)
    report = filter_docs_catalog(
        catalog,
        tag=str(getattr(args, "tag", "") or ""),
        concern_lane=str(getattr(args, "concern", "") or ""),
        lifecycle_lane=str(getattr(args, "lifecycle", "") or ""),
        audience_lane=str(getattr(args, "audience", "") or ""),
        phase=str(getattr(args, "phase", "") or ""),
        doc_type=str(getattr(args, "doc_type", "") or ""),
        query=str(getattr(args, "query", "") or ""),
        has_linked_symbols=has_links,
        limit=int(getattr(args, "limit", 50) or 50),
    )

    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        ui.ok("Docs catalog")
        ui.kv("Cache", "hit" if report.get("cache_hit") else "rebuilt")
        ui.kv("Cache path", report.get("cache_path"))
        ui.kv("Generated", report.get("generated_at"))
        stats = report.get("stats") or {}
        ui.kv("Documents indexed", stats.get("document_count"))
        ui.kv("Unique tags", stats.get("unique_tags"))
        ui.kv("Matches", report.get("match_count"))
        ui.blank()
        tags = report.get("tags") or []
        if tags and not any(
            (
                getattr(args, "tag", None),
                getattr(args, "query", None),
                getattr(args, "concern", None),
            )
        ):
            ui.kv("Top tags", ", ".join(f"{t['tag']}({t['count']})" for t in tags[:20]))
            ui.blank()
        for row in (report.get("documents") or [])[: int(getattr(args, "limit", 50) or 50)]:
            title = row.get("title") or "(no title)"
            print(f"- {row.get('path')}")
            print(
                f"  {title} | concern={row.get('concern_lane') or '-'} "
                f"| life={row.get('lifecycle_lane') or '-'} "
                f"| tags={','.join(row.get('tags') or []) or '-'}"
            )
        ui.blank()
        ui.kv(
            "Hint",
            "filter with --tag/--concern/--query; --refresh rebuilds cache; "
            "does not invent DOCUMENTED_BY",
        )
        ui.blank()

    return 0 if int(report.get("match_count") or 0) >= 0 else 1
