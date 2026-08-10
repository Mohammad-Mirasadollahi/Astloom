"""`astloom pack review` — change-scoped export with secret scan + token budget."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from astloom_cli.util import print_json, repo_root


def _paths_from_stdin() -> list[str]:
    if sys.stdin.isatty():
        return []
    return [ln.strip().replace("\\", "/") for ln in sys.stdin.read().splitlines() if ln.strip()]


def cmd_pack_review(args: argparse.Namespace) -> int:
    from repo_pack.review_pack import build_review_pack, git_changed_files

    raw_root = str(getattr(args, "root", None) or "").strip()
    # RM-15: no remote/template pack paths — local roots only (default deny).
    lowered = raw_root.lower()
    if (
        "://" in raw_root
        or lowered.startswith(("http:", "https:", "git@", "ssh:", "git://"))
        or raw_root.startswith("git@")
    ):
        print_json(
            {
                "ok": False,
                "error": "remote_root_denied",
                "note": "astloom pack review is local-only (RM-15 / no-cloud-exfiltration)",
            }
        )
        return 2

    root = Path(raw_root or repo_root()).expanduser().resolve()
    files: list[str] = []
    raw_files = getattr(args, "files", None) or ""
    if raw_files:
        files.extend(p.strip() for p in str(raw_files).split(",") if p.strip())
    if getattr(args, "from_git", False) or getattr(args, "staged", False):
        files.extend(git_changed_files(root, staged=bool(getattr(args, "staged", False))))
    if getattr(args, "stdin", False):
        files.extend(_paths_from_stdin())
    # Dedupe preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            ordered.append(f)
    if not ordered:
        print_json(
            {
                "ok": False,
                "error": "no files: pass --files a,b, --from-git / --staged, or --stdin",
            }
        )
        return 2

    budget = getattr(args, "token_budget", None)
    hotspot_min = getattr(args, "hotspot_min_tokens", None)
    result = build_review_pack(
        root,
        ordered,
        include_diff=bool(getattr(args, "include_diff", False)),
        staged=bool(getattr(args, "staged", False)),
        max_file_bytes=int(getattr(args, "max_file_bytes", 200_000) or 200_000),
        token_budget=int(budget) if budget is not None else None,
        fail_on_secrets=not bool(getattr(args, "allow_secrets", False)),
        hotspot_min_tokens=int(hotspot_min) if hotspot_min is not None else 50,
    )
    out_path = getattr(args, "out", None)
    if out_path and result.ok:
        Path(out_path).expanduser().write_text(result.markdown, encoding="utf-8")

    payload = result.public()
    if out_path:
        payload["written"] = str(Path(out_path).expanduser().resolve()) if result.ok else None
    if getattr(args, "json", False) or not result.ok:
        print_json(payload)
    else:
        print(f"files:             {len(result.files)}")
        print(f"total_chars:       {result.total_chars}")
        print(f"estimated_tokens:  {result.estimated_tokens}")
        print(f"secret_findings:   {len(result.secret_findings)}")
        print(f"ignored_skipped:   {len(result.ignored_skipped)}")
        print(f"over_token_budget: {result.over_token_budget}")
        if result.hotspots:
            print("hotspots:")
            for row in result.hotspots[:10]:
                print(f"  {row['estimated_tokens']:>6}  {row['path']}")
        if out_path:
            print(f"written:           {payload.get('written')}")
        else:
            print("---")
            print(result.markdown)

    if not result.ok:
        return 2
    return 0
