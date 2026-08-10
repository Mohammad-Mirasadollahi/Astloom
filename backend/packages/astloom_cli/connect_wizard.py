"""Interactive first-time / edit onboarding for `astloom connect` (HTTPS)."""

from __future__ import annotations

import getpass
import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable

from astloom_cli import ui
from astloom_cli.connect_config import (
    ConnectSettings,
    default_connect_yaml_path,
    try_resolve_config_path,
    write_or_merge_connect_yaml,
)


PromptFn = Callable[[str], str]
PasswordFn = Callable[[str], str]


def _require_tty() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SystemExit(
            "error: interactive HTTPS setup needs a TTY; "
            "create .astloom/connect.yaml (astloom connect init) "
            "or run from a terminal: astloom connect / astloom connect edit"
        )


def _prompt_line(prompt: str, *, default: str = "", input_fn: PromptFn = input) -> str:
    suffix = f" [{default}]" if default else ""
    raw = input_fn(f"{prompt}{suffix}: ").strip()
    return raw or default


def mask_api_key(token: str) -> str:
    text = (token or "").strip()
    if len(text) <= 8:
        return "****"
    return f"{text[:4]}…{text[-4:]}"


def prompt_api_key(
    *,
    existing: str = "",
    config_path: Path | None = None,
    password_fn: PasswordFn = getpass.getpass,
) -> str:
    """Require an API access token; blank Enter keeps an existing one."""
    from astloom_cli.connect_http import read_access_token_file

    current = (existing or "").strip() or read_access_token_file(config_path)
    if current:
        raw = password_fn(
            f"API key [{mask_api_key(current)}] (Enter=keep, or paste new): "
        ).strip()
        return raw or current
    raw = password_fn("API key (as1.* required): ").strip()
    if not raw:
        raise SystemExit(
            "error: API key is required for connect "
            "(paste an as1.* key, or set ASTLOOM_TOKEN / .astloom/access_token)"
        )
    return raw


def prompt_usage_profile(
    *,
    default: str = "",
    input_fn: PromptFn = input,
) -> str:
    """Resolve Usage Profile id from catalog. Single catalog entry is auto-selected."""
    from usage_profile import list_profile_ids, load_usage_profile

    ids = list(list_profile_ids())
    if not ids:
        raise SystemExit("error: no Usage Profiles installed (usage_profile catalog empty)")
    if len(ids) == 1:
        only = ids[0]
        print(f"   {ui.ok('✔')} Usage Profile: {only}")
        return only
    ui.blank()
    print("   Usage Profiles (choose at connect — not set during client install):")
    for index, profile_id in enumerate(ids, start=1):
        try:
            title = str(load_usage_profile(profile_id).get("title") or "")
        except Exception:  # noqa: BLE001 — listing must not fail on one bad profile
            title = ""
        label = f"{profile_id}" + (f" — {title}" if title else "")
        mark = " *" if profile_id == default else ""
        print(f"     {index}) {label}{mark}")
    ui.blank()
    hint = default if default in ids else ""
    while True:
        raw = _prompt_line("Usage Profile id or number", default=hint, input_fn=input_fn).strip()
        if not raw:
            raise SystemExit(
                "error: Usage Profile is required at connect "
                "(pass --usage-profile or choose interactively)"
            )
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(ids):
                return ids[idx - 1]
            print(f"   {ui.warn('!')} enter 1–{len(ids)} or a profile id")
            continue
        if raw in ids:
            return raw
        print(f"   {ui.warn('!')} unknown profile {raw!r}; pick from the list")


def run_https_connect_wizard(
    *,
    existing: ConnectSettings | None = None,
    config_path: Path | None = None,
    project_dir: Path | None = None,
    url_override: str = "",
    input_fn: PromptFn = input,
    password_fn: PasswordFn = getpass.getpass,
) -> ConnectSettings:
    """Prompt for HTTPS URL, API key, and optional bootstrap secret; write connect.yaml.

    The bootstrap HTTP call (register project / optional mint) runs later in
    ``run_connect``. The API key is required here and saved next to connect.yaml.
    """
    _require_tty()
    work = project_dir or Path.cwd()
    base = existing or ConnectSettings()
    target = config_path or try_resolve_config_path() or default_connect_yaml_path()

    ui.blank()
    ui.heading("HTTPS connect setup")
    ui.blank()
    ui.bullet("API key (as1.*) is required for MCP and sync; stored in .astloom/access_token.")
    ui.bullet("Existing key: Enter keeps it; paste a new value to replace.")
    ui.bullet("Bootstrap secret authenticates first register only; it is never saved.")
    ui.blank()

    url = _prompt_line(
        "Astloom server URL (https://…)",
        default=url_override or base.api_url,
        input_fn=input_fn,
    ).rstrip("/")
    if not url:
        raise SystemExit("error: server URL is required")
    if url.split("://", 1)[0].lower() != "https":
        raise SystemExit(f"error: HTTPS connect requires an https:// URL, got {url!r}")

    tenant = _prompt_line("Tenant", default=base.tenant or "default", input_fn=input_fn)
    workspace = _prompt_line("Workspace", default=base.workspace or "default", input_fn=input_fn)
    usage_profile = (base.usage_profile or "").strip() or prompt_usage_profile(
        default=(base.usage_profile or "").strip(),
        input_fn=input_fn,
    )
    project = base.project or work.name or "project"
    api_token = prompt_api_key(
        existing=base.api_token,
        config_path=target,
        password_fn=password_fn,
    )
    secret = password_fn(f"Bootstrap secret for {url} (blank if none configured): ")

    settings = replace(
        base,
        api_url=url,
        tenant=tenant,
        workspace=workspace,
        project=project,
        project_name=base.project_name or project,
        usage_profile=usage_profile,
        prefer_http=True,
        local=False,
        register=True,
        bootstrap_secret=secret,
        api_token=api_token,
        config_path=target,
    )
    secret = ""

    written = write_or_merge_connect_yaml(settings, path=target, prefer_http=True)
    from astloom_cli.connect_http import persist_access_token

    token_path = persist_access_token(target, api_token)
    print(f"   {ui.ok('✔')} wrote {written}")
    if token_path is not None:
        print(f"   {ui.ok('✔')} API key saved ({token_path.name}; mode 0600)")
    print(f"   {ui.ok('✔')} HTTPS target {settings.api_url}")
    return settings
