"""`astloom connect` — one-command coding-agent onboarding."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from astloom_cli.connect_config import (
    ConnectSettings,
    default_connect_yaml_path,
    load_connect_settings,
    try_resolve_config_path,
    write_connect_template,
    write_or_merge_connect_yaml,
)
from astloom_cli.connect_flow import run_connect
from astloom_cli.connect_flow.source_path import source_path_for_connect as _source_path_for_connect
from astloom_cli.connect_wizard import run_https_connect_wizard


def parse_connect_project_dirs(
    raw: str,
    *,
    cwd: Path | None = None,
) -> list[Path]:
    """Parse comma-separated project directories (default: cwd)."""
    work = (cwd or Path.cwd()).resolve()
    text = (raw or "").strip()
    if not text:
        return [work]
    out: list[Path] = []
    seen: set[str] = set()
    for part in text.split(","):
        piece = part.strip()
        if not piece:
            continue
        path = Path(piece).expanduser().resolve()
        if not path.is_dir():
            raise SystemExit(f"error: connect path is not a directory: {path}")
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    if not out:
        raise SystemExit("error: no connect paths given (use cwd or PATH[,PATH…])")
    return out


def _parse_connect_target(raw: str) -> tuple[str, str]:
    """Return (mode, path_spec). mode is edit|init|'' ; path_spec is comma paths or ''."""
    text = (raw or "").strip()
    if not text:
        return "", ""
    lower = text.lower()
    if lower in {"edit", "init"}:
        return lower, ""
    if "," in text or "/" in text or text.startswith(".") or text.startswith("~"):
        return "", text
    # Bare token that is not edit/init — treat as a single relative/absolute path name.
    return "", text


def _settings_for_local(args: argparse.Namespace, *, work: Path) -> ConnectSettings:
    """Same-host connect: scope from flags → identity/env/connect.yaml (not hardcoded dogfood)."""
    from astloom_cli.cli_defaults import resolve_operator_scope

    tenant, workspace, project = resolve_operator_scope(
        tenant=str(args.tenant or ""),
        workspace=str(args.workspace or ""),
        project=str(args.project or ""),
        cwd=work,
    )
    return ConnectSettings(
        local=True,
        remote_root=str(Path(args.remote_root).resolve()) if args.remote_root else str(work),
        tenant=tenant,
        workspace=workspace,
        project=project,
        project_name=project,
        usage_profile=str(getattr(args, "usage_profile", "") or "").strip(),
        clients=str(args.clients or "all"),
        include_user_clients=bool(args.include_user_clients),
        register=True,
        smoke_test=False,
        ingest_mode="off",
        source_server_path=str(work),
        prefer_http=False,
    )


def _ensure_usage_profile(
    settings: ConnectSettings,
    args: argparse.Namespace,
    *,
    allow_prompt: bool,
) -> ConnectSettings:
    """Usage Profile is selected at connect time — never baked in at client install."""
    override = str(getattr(args, "usage_profile", "") or "").strip()
    if override:
        return replace(settings, usage_profile=override)
    if (settings.usage_profile or "").strip():
        return settings
    from usage_profile import list_profile_ids

    ids = list(list_profile_ids())
    if len(ids) == 1:
        return replace(settings, usage_profile=ids[0])
    if allow_prompt and sys.stdin.isatty() and sys.stdout.isatty():
        from astloom_cli.connect_wizard import prompt_usage_profile

        return replace(settings, usage_profile=prompt_usage_profile())
    raise SystemExit(
        "error: Usage Profile required at connect "
        "(pass --usage-profile ID, or run interactively to choose)"
    )


def _ensure_api_key(
    settings: ConnectSettings,
    *,
    allow_prompt: bool,
    config_path: Path | None,
) -> ConnectSettings:
    """Require API key for remote connect; on TTY offer keep-or-replace."""
    if settings.local:
        return settings
    target = config_path or settings.config_path
    if allow_prompt and sys.stdin.isatty() and sys.stdout.isatty():
        from astloom_cli.connect_http import persist_access_token
        from astloom_cli.connect_wizard import prompt_api_key

        token = prompt_api_key(existing=settings.api_token, config_path=target)
        if target is not None:
            persist_access_token(target, token)
        return replace(settings, api_token=token, config_path=target or settings.config_path)
    if (settings.api_token or "").strip():
        return settings
    raise SystemExit(
        "error: API key required for connect "
        "(set ASTLOOM_TOKEN, write .astloom/access_token, or run interactively)"
    )


def _config_path_from_args(args: argparse.Namespace, *, project_dir: Path) -> Path | None:
    explicit = str(args.config or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return try_resolve_config_path(project_root=project_dir)


def _pin_software_paths(settings: ConnectSettings, roots: list[Path]) -> None:
    """Remember connected project dirs so later ``astloom sync`` uses them."""
    from astloom_cli.software_paths import normalize_software_paths, peek_software_paths, persist_software_paths

    merged = normalize_software_paths(
        [*peek_software_paths(), *[str(p) for p in roots]],
        must_exist=True,
    )
    persist_software_paths(
        merged,
        tenant=settings.tenant,
        workspace=settings.workspace,
        project=settings.project,
        display_name=settings.project_name or settings.project,
    )


def _persist_and_run_connect(
    settings: ConnectSettings,
    *,
    work: Path,
    yaml_path: Path,
    dry_run: bool,
) -> tuple[int, ConnectSettings]:
    """Persist connect.yaml (unless dry-run/local), then run_connect."""
    if not dry_run and not settings.local:
        write_or_merge_connect_yaml(settings, path=yaml_path, prefer_http=settings.prefer_http)
        if settings.config_path is None:
            settings = replace(settings, config_path=yaml_path)
    code = run_connect(settings, project_dir=work, dry_run=dry_run)
    return code, settings


def _connect_one(
    args: argparse.Namespace,
    *,
    work: Path,
    shared: ConnectSettings | None,
    force_edit: bool,
) -> tuple[int, ConnectSettings]:
    """Connect a single project directory. Reuse *shared* settings when provided."""
    project_override = str(args.project or "").strip()
    project_id = project_override or work.name or "project"
    dry_run = bool(args.dry_run)
    allow_prompt = not dry_run

    if args.local and not args.config:
        settings = _settings_for_local(args, work=work)
        if not project_override:
            settings = replace(settings, project=project_id, project_name=project_id)
        settings = replace(
            settings,
            source_server_path=_source_path_for_connect(local=True, work=work),
        )
        settings = _ensure_usage_profile(
            settings, args, allow_prompt=allow_prompt
        )
        code = run_connect(settings, project_dir=work, dry_run=dry_run)
        return code, settings

    cfg = _config_path_from_args(args, project_dir=work)
    yaml_path = default_connect_yaml_path(work)

    if shared is not None:
        settings = replace(
            shared,
            project=project_id,
            project_name=project_override or shared.project_name or project_id,
            source_server_path=_source_path_for_connect(
                local=bool(shared.local),
                work=work,
                configured=shared.source_server_path,
            ),
        )
        if args.include_user_clients:
            settings = replace(settings, include_user_clients=True)
        settings = _ensure_usage_profile(
            settings, args, allow_prompt=allow_prompt
        )
        return _persist_and_run_connect(
            settings,
            work=work,
            yaml_path=yaml_path,
            dry_run=dry_run,
        )

    if cfg is None and not args.local:
        existing = ConnectSettings(
            project=project_id,
            project_name=project_id,
            clients=str(args.clients or "all"),
            include_user_clients=bool(args.include_user_clients),
            tenant=str(args.tenant or "default"),
            workspace=str(args.workspace or "default"),
            usage_profile=str(getattr(args, "usage_profile", "") or "").strip(),
            prefer_http=True,
            source_server_path="",
        )
        settings = run_https_connect_wizard(
            existing=existing,
            config_path=yaml_path,
            project_dir=work,
            url_override=str(args.server or "").strip(),
        )
        if args.include_user_clients:
            settings = replace(settings, include_user_clients=True)
        settings = replace(
            settings,
            source_server_path=_source_path_for_connect(
                local=False,
                work=work,
                configured=settings.source_server_path,
            ),
        )
        settings = _ensure_usage_profile(
            settings, args, allow_prompt=allow_prompt
        )
        return _persist_and_run_connect(
            settings,
            work=work,
            yaml_path=yaml_path,
            dry_run=dry_run,
        )

    settings = load_connect_settings(
        config_path=str(args.config or "") or (str(cfg) if cfg else ""),
        project_override=project_override,
        api_url_override=str(args.server or ""),
        clients_override=str(args.clients or ""),
        cwd=work,
        allow_incomplete=force_edit,
        project_root=work,
    )
    if args.local:
        settings = replace(settings, local=True, prefer_http=False)
    if args.include_user_clients:
        settings = replace(settings, include_user_clients=True)
    if args.tenant:
        settings = replace(settings, tenant=str(args.tenant))
    if args.workspace:
        settings = replace(settings, workspace=str(args.workspace))
    settings = replace(
        settings,
        source_server_path=_source_path_for_connect(
            local=bool(settings.local or args.local),
            work=work,
            configured=settings.source_server_path,
        ),
    )

    if force_edit and not settings.local:
        settings = run_https_connect_wizard(
            existing=settings,
            config_path=cfg or yaml_path,
            project_dir=work,
            url_override=str(args.server or "").strip(),
        )
    elif not settings.local:
        settings = _ensure_api_key(
            settings,
            allow_prompt=allow_prompt,
            config_path=cfg or yaml_path,
        )

    settings = _ensure_usage_profile(
        settings, args, allow_prompt=allow_prompt
    )
    if settings.local:
        code = run_connect(settings, project_dir=work, dry_run=dry_run)
        return code, settings
    return _persist_and_run_connect(
        settings,
        work=work,
        yaml_path=cfg or yaml_path,
        dry_run=dry_run,
    )


def cmd_connect(args: argparse.Namespace) -> int:
    mode, path_spec = _parse_connect_target(str(getattr(args, "connect_mode", "") or ""))
    if mode == "init":
        path = write_connect_template(default_connect_yaml_path(Path.cwd()))
        print(f"wrote {path}")
        print("Edit connect.yaml (local / https), then run: astloom connect")
        return 0

    cwd = Path.cwd()
    roots = parse_connect_project_dirs(path_spec, cwd=cwd)
    force_edit = mode == "edit"

    if force_edit and len(roots) > 1:
        raise SystemExit("error: connect edit applies to one project dir (omit PATH[,PATH…] or pass a single path)")

    shared: ConnectSettings | None = None
    last_code = 0
    for index, work in enumerate(roots):
        if len(roots) > 1:
            print(f"\n=== connect {index + 1}/{len(roots)}: {work} ===\n")
        code, settings = _connect_one(
            args,
            work=work,
            shared=shared,
            force_edit=force_edit,
        )
        if code != 0:
            last_code = code
            break
        if index == 0 and len(roots) > 1 and not settings.local:
            shared = settings
        last_code = code

    if last_code == 0 and not bool(args.dry_run):
        # Pin all connected dirs for sync (cwd alone, or every comma-separated path).
        try:
            _pin_software_paths(settings, roots)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001 — pin is best-effort after successful connect
            print(f"warning: could not pin software paths for sync: {exc}", flush=True)

    return last_code
