"""``astloom docs-suggest-links`` — hybrid evidence-only link suggestions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from astloom_cli import ui
from astloom_cli.docs_link_suggest import (
    apply_suggested_links,
    suggest_links_for_markdown,
    suggest_links_for_tree,
)
from astloom_cli.util import repo_root


def cmd_docs_suggest_links(args: argparse.Namespace) -> int:
    root = repo_root().resolve()
    apply = bool(getattr(args, "apply", False))
    path_arg = str(getattr(args, "path", "") or "").strip()
    as_json = bool(getattr(args, "json", False))
    docs_root = str(getattr(args, "docs_root", "") or "docs").strip() or "docs"
    include_all = bool(getattr(args, "include_all", False))
    apply_results: list[dict] = []

    if path_arg:
        target = Path(path_arg)
        if not target.is_absolute():
            target = root / target
        if not target.is_file():
            ui.err(f"file not found: {path_arg}")
            return 2
        rel = str(target.resolve().relative_to(root)).replace("\\", "/")
        row = suggest_links_for_markdown(
            relative_path=rel,
            text=target.read_text(encoding="utf-8", errors="replace"),
            repo=root,
        )
        # Always include the single-file row (empty / already-linked / missing FM).
        report = {
            "repo": str(root),
            "docs_root": None,
            "scanned_count": 1,
            "files_with_suggestions": 1 if row["suggested_new"] else 0,
            "suggested_total": len(row["suggested_new"]),
            "include_all": include_all,
            "files": [row],
            "mode": "hybrid_evidence_suggest",
        }
        if apply:
            apply_results.append(apply_suggested_links(target, row["suggested_new"]))
    else:
        report = suggest_links_for_tree(
            root,
            docs_root=docs_root,
            include_all=include_all,
        )
        if apply:
            for row in report.get("files") or []:
                if not row.get("suggested_new"):
                    continue
                apply_results.append(
                    apply_suggested_links(root / row["file"], row["suggested_new"])
                )

    if apply:
        report["apply_results"] = apply_results
        report["applied_count"] = sum(
            1 for r in apply_results if r.get("status") == "applied"
        )
        report["skipped_no_frontmatter_count"] = sum(
            1 for r in apply_results if r.get("status") == "skipped_no_frontmatter"
        )

    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        ui.ok("Docs suggest-links (hybrid evidence)")
        ui.kv("Repo", report.get("repo"))
        if report.get("docs_root") is not None:
            ui.kv("Docs root", report.get("docs_root"))
        ui.kv("Scanned", report.get("scanned_count"))
        ui.kv("Files with suggestions", report.get("files_with_suggestions"))
        ui.kv("Suggested new tokens", report.get("suggested_total"))
        for row in (report.get("files") or [])[:40]:
            ui.blank()
            ui.kv("File", row["file"])
            ui.kv("Has frontmatter", row.get("has_frontmatter"))
            for token in row.get("suggested_new") or []:
                print(f"  + {token}")
            if include_all and not row.get("suggested_new"):
                already = row.get("already_linked") or []
                if already:
                    ui.kv("Already linked", ", ".join(already[:8]))
                else:
                    ui.kv("Suggestions", "(none)")
        if apply:
            ui.blank()
            ui.kv("Applied", report.get("applied_count", 0))
            ui.kv("Skipped (no frontmatter)", report.get("skipped_no_frontmatter_count", 0))
            ui.kv("Next", "astloom sync (Phase 2 writes DOCUMENTED_BY for resolved tokens)")
        else:
            ui.blank()
            ui.kv("Hint", "dry-run only; pass --apply to write linked_symbols, then sync")
        ui.blank()

    return 0 if int(report.get("suggested_total") or 0) == 0 else 1
