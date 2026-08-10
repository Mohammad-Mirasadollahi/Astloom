#!/usr/bin/env python3
"""Baseline stamp: set doc_version=1.0.0 and updated_at=<date> on product Markdown.

Usage:
  python scripts/stamp_docs_revision.py
  python scripts/stamp_docs_revision.py --date 2026-07-24 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "backend" / "packages"),
    str(ROOT / "backend" / "services" / "code-graph-service" / "src"),
]

from astloom_cli.commands.docs_standards.stamp_revision import (  # noqa: E402
    DEFAULT_DOC_VERSION,
    stamp_revision_tree,
)

DEFAULT_ROOTS = (
    "docs",
    "backend/docs",
    "frontend/docs",
    "deploy-toolkit",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        default="2026-07-24",
        help="UTC calendar date for updated_at (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_DOC_VERSION,
        help=f"doc_version to set (default {DEFAULT_DOC_VERSION})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing files",
    )
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Extra/override scan root relative to repo (repeatable)",
    )
    args = parser.parse_args()
    roots = [ROOT / r for r in (args.root or list(DEFAULT_ROOTS))]
    result = stamp_revision_tree(
        roots,
        repo=ROOT,
        doc_version=str(args.version),
        updated_at=str(args.date),
        write=not bool(args.dry_run),
    )
    summary = result["summary"]
    out = ROOT / ".astloom" / "docs-revision-stamp-result.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"dry_run={bool(args.dry_run)}",
        f"doc_version={summary['doc_version']}",
        f"updated_at={summary['updated_at']}",
        f"changed={summary['changed']}",
        f"unchanged={summary['unchanged']}",
        f"skipped_no_frontmatter={summary['skipped_no_frontmatter']}",
        f"errors={summary['errors']}",
    ]
    for rel in result["changed"][:80]:
        lines.append(f"CHANGED {rel}")
    if len(result["changed"]) > 80:
        lines.append(f"... +{len(result['changed']) - 80} more")
    for rel in result["skipped_no_frontmatter"][:40]:
        lines.append(f"SKIP_NO_FM {rel}")
    for err in result["errors"][:20]:
        lines.append(f"ERROR {err}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
