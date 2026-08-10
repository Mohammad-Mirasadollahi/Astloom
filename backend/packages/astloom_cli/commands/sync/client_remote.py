"""Client checkout: content-push sync via connect.yaml.

Local discovery -> remote ``ingest-push`` over HTTPS (no durable checkout on
the Astloom host).
"""

from __future__ import annotations

import argparse
from pathlib import Path


def cmd_sync_client_remote(args: argparse.Namespace) -> int:
    from astloom_cli.connect_config import (
        load_connect_settings,
        try_resolve_config_path,
    )
    from astloom_cli.connect_flow.client_push import client_push_sync
    from astloom_cli.service_runtime.paths import missing_local_stack_message
    from astloom_cli.util import repo_root

    cfg = try_resolve_config_path()
    if cfg is None:
        raise SystemExit(missing_local_stack_message(repo_root()))
    settings = load_connect_settings(config_path=str(cfg), allow_incomplete=True)
    http_ready = bool(
        (settings.graph_url or "").strip() and (settings.api_token or "").strip()
    )
    if not http_ready:
        raise SystemExit(missing_local_stack_message(repo_root()))

    return client_push_sync(settings, args, work=Path.cwd())


# Compat alias.
_cmd_sync_client_remote = cmd_sync_client_remote
