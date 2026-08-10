"""Local and remote ingest helpers used during connect / sync."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from astloom_cli import ui
from astloom_cli.connect_config import ConnectSettings
from astloom_cli.util import repo_root


def remote_ingest(settings: ConnectSettings, *, work: Path | None = None) -> int:
    """Ingest after connect via content-push (HTTPS)."""
    root = work or Path.cwd()
    can_push = bool((settings.graph_url or "").strip() and (settings.api_token or "").strip())
    if not can_push:
        return 0
    from astloom_cli.connect_flow.client_push import client_push_sync

    return client_push_sync(
        settings,
        SimpleNamespace(
            tenant=settings.tenant,
            workspace=settings.workspace,
            project=settings.project,
            path=None,
            allow_cloud_llm=False,
            max_files=None,
            sync_mode="",
            exclude_dir=[],
            include_path=[],
            include_ext=[],
        ),
        work=root,
    )


def local_ingest(settings: ConnectSettings, path: str) -> int:
    root = repo_root()
    astloom = root / ".venv" / "bin" / "astloom"
    exe = str(astloom if astloom.is_file() else "astloom")
    print(f"   {ui.warn('…')} syncing {path} (local)")
    return subprocess.run(
        [
            exe,
            "sync",
            "--tenant",
            settings.tenant,
            "--workspace",
            settings.workspace,
            "--project",
            settings.project,
            "--path",
            path,
        ],
        cwd=str(root),
    ).returncode


def should_ingest(settings: ConnectSettings) -> bool:
    mode = settings.ingest_mode
    if mode == "off":
        return False
    can_push = bool((settings.graph_url or "").strip() and (settings.api_token or "").strip())
    if not can_push and not (settings.source_server_path or settings.source_git_remote):
        return False
    if mode == "always":
        return True
    return mode in ("optional", "if_source", "true", "yes")


_local_ingest = local_ingest
_should_ingest = should_ingest
