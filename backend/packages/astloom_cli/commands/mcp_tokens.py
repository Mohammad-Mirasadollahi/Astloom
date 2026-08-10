"""`astloom mcp tokens` — connect estimate + usage history by client/scope id."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from astloom_cli.mcp_token_report import build_report, format_text
from astloom_cli.util import print_json, repo_root


def _ensure_gateway_imports() -> None:
    root = repo_root()
    for rel in (
        ("backend", "services", "mcp-gateway-service", "src"),
        ("backend", "services", "common-context-service", "src"),
        ("backend", "packages"),
    ):
        path = root.joinpath(*rel)
        text = str(path)
        if path.is_dir() and text not in sys.path:
            sys.path.insert(0, text)


def cmd_mcp_tokens(args: argparse.Namespace) -> int:
    _ensure_gateway_imports()
    project_dir = Path(args.project_dir).expanduser().resolve() if args.project_dir else Path.cwd()
    report = build_report(
        usage_profile=str(args.usage_profile or "programming-cursor-mcp"),
        since=str(args.since or "") or None,
        until=str(args.until or "") or None,
        clients_raw=str(args.clients or "all"),
        scope_ids_raw=str(args.id or "all"),
        project_dir=project_dir,
        include_user_clients=bool(args.include_user_clients),
    )
    if str(args.format or "text") == "json":
        print_json(report)
    else:
        print(format_text(report))
    return 0
