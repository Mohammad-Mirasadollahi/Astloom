"""Code-graph operator CLI commands."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from ipaddress import ip_address
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from astloom_cli.parser._core import resolve_discovery_max_files
from astloom_cli.util import now_iso, print_json, repo_root, require_scope


def _ensure_code_graph_import() -> None:
    root = repo_root()
    src = root / "backend" / "services" / "code-graph-service" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _graph_service():
    """In-process code-graph service (auto neo4j when password set; else memory).

    Reuses one composition root per process (Phase D DI).
    """
    from astloom_cli.cli_defaults import load_dotenv_files
    from astloom_cli.process_containers import get_graph_service

    load_dotenv_files()
    _ensure_code_graph_import()
    backend = os.environ.get("ASTLOOM_GRAPH_CLI_BACKEND", "").strip().lower()
    if not backend:
        pwd = os.environ.get("ASTLOOM_NEO4J_PASSWORD", "").strip()
        backend = "neo4j" if pwd and pwd not in {
            "replace-with-a-local-secret",
            "changeme",
            "password",
            "neo4j",
        } else "memory"

    def _factory():
        if backend == "neo4j":
            try:
                from astloom_cli.remote_client import apply_compose_env_to_os

                apply_compose_env_to_os(os.environ, repo_root())
            except SystemExit:
                pass
            from code_graph_service.bootstrap import Settings, build_container

            return build_container(Settings.from_environment())
        from code_graph_service.core import CodeGraphService
        from code_graph_service.testing import InMemoryStore

        return CodeGraphService(InMemoryStore())

    return get_graph_service(backend=backend, factory=_factory)


def _read_cloud_llm_yes_no(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError as exc:
        raise SystemExit(
            "error: cloud LLM consent aborted (no input). Nothing was synced."
        ) from exc


def _require_cloud_llm_consent(
    svc,
    *,
    allowed: bool,
    tenant: str = "",
    workspace: str = "",
    project: str = "",
    paths: Sequence[str | Path] | None = None,
    input_fn: Any | None = None,
    stdin_isatty: bool | None = None,
    may_send_code_prompts: bool = True,
) -> bool:
    """Fail closed on non-private LLM routes unless flag or interactive yes.

    Returns True when this run is explicitly allowed (flag or interactive consent)
    so remote HTTPS sync can forward ``--allow-cloud-llm``. Returns False when the
    route is disabled/private (no flag needed).

    When ``may_send_code_prompts`` is False (e.g. noop sync with no code ingest and
    cloud embeddings disabled), skip the gate — nothing will leave the private boundary.
    """
    if not may_send_code_prompts:
        return False
    config = svc.llm_config()
    if not config.get("enabled"):
        return False
    models: list[str] = []
    for enabled_key, route_key in (
        ("docs_enabled", "route_docs"),
        ("embeddings_enabled", "route_embed"),
    ):
        if not config.get(enabled_key):
            continue
        route = config.get(route_key) or {}
        models.extend(
            model
            for model in [route.get("primary_model"), *(route.get("fallback_models") or [])]
            if isinstance(model, str) and model.strip()
        )
    if not models:
        return False
    host = urlparse(str(config.get("api_base") or "")).hostname or ""
    try:
        loopback = ip_address(host).is_loopback
    except ValueError:
        loopback = False
    local_prefixes = ("local/", "localai/", "lm_studio/", "ollama/", "ollama_chat/", "hosted_vllm/")
    private_route = loopback and all(model.lower().startswith(local_prefixes) for model in models)
    if private_route:
        return False
    if allowed:
        return True

    path_list = [str(Path(p)) for p in (paths or [])]
    tty = sys.stdin.isatty() if stdin_isatty is None else bool(stdin_isatty)
    if not tty:
        raise SystemExit(
            "error: LLM route may leave the private boundary; "
            "rerun in an interactive terminal to consent, "
            "or pass --allow-cloud-llm after explicit per-run consent, "
            "or configure a loopback local model (ollama/localai/lm_studio/hosted_vllm)"
        )

    from astloom_cli import ui

    ui.blank()
    ui.heading("Cloud LLM consent required", success=False)
    ui.blank()
    ui.kv("Tenant", tenant or "?")
    ui.kv("Workspace", workspace or "?")
    ui.kv("Project", project or "?")
    if path_list:
        if len(path_list) == 1:
            ui.kv("Path", path_list[0])
        else:
            for idx, path in enumerate(path_list, start=1):
                ui.kv(f"Path {idx}", path)
    else:
        ui.kv("Path", "(none — query only)")
    ui.kv("API host", host or "?")
    ui.kv("Models", ", ".join(models[:8]))
    ui.blank()
    ui.bullet("Code-derived prompts may leave the private boundary for this run.")
    ui.blank()
    read = input_fn or _read_cloud_llm_yes_no
    answer1 = read("1/2  Allow cloud LLM for this run? [y/N]: ").strip().lower()
    if answer1 not in {"y", "yes"}:
        raise SystemExit("error: cloud LLM consent declined. Nothing was synced.")

    scope_id = f"{tenant or '?'}/{workspace or '?'}/{project or '?'}"
    ui.blank()
    ui.section("Confirm scope IDs")
    ui.kv("IDs", scope_id)
    if path_list:
        if len(path_list) == 1:
            ui.kv("Path", path_list[0])
        else:
            for idx, path in enumerate(path_list, start=1):
                ui.kv(f"Path {idx}", path)
    else:
        ui.kv("Path", "(none — query only)")
    ui.blank()
    answer2 = read(
        "2/2  Confirm these IDs and path will be used? [y/N]: "
    ).strip().lower()
    if answer2 not in {"y", "yes"}:
        raise SystemExit("error: scope ID confirmation declined. Nothing was synced.")
    return True



def _graph_scope(args: argparse.Namespace, *, with_defaults: bool = False):
    _ensure_code_graph_import()
    from code_graph_service.core import Scope

    tenant, workspace, project = require_scope(args, with_defaults=with_defaults)
    return Scope(tenant, workspace, project)


def cmd_graph_ingest(args: argparse.Namespace) -> int:
    svc = _graph_service()
    scope = _graph_scope(args)
    root_path = Path(args.path).resolve()
    if not root_path.is_dir():
        raise SystemExit(f"error: path is not a directory: {root_path}")
    _require_cloud_llm_consent(
        svc,
        allowed=bool(getattr(args, "allow_cloud_llm", False)),
        tenant=scope.tenant_id,
        workspace=scope.workspace_id,
        project=scope.project_id,
        paths=[root_path],
    )
    result = svc.ingest_repo(
        scope,
        "cli",
        f"cli-{now_iso()}",
        f"cli-repo:{root_path}",
        {
            "root_path": str(root_path),
            "include_extensions": [".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"],
            "max_files": resolve_discovery_max_files(getattr(args, "max_files", 0)),
            "include_outcomes": True,
        },
    )
    payload = result.to_dict() if hasattr(result, "to_dict") else result
    refresh = payload.get("embedding_refresh") or {}
    ok = int(payload.get("files_failed") or 0) == 0 and refresh.get("state") != "failed"
    print_json({"ok": ok, "path": str(root_path), "result": payload})
    return 0 if ok else 1


def cmd_graph_freshness(args: argparse.Namespace) -> int:
    svc = _graph_service()
    scope = _graph_scope(args)
    if args.mark_pending:
        svc.mark_file_pending(args.mark_pending)
    print_json(svc.freshness_status(scope))
    return 0


def cmd_graph_explore(args: argparse.Namespace) -> int:
    svc = _graph_service()
    scope = _graph_scope(args)
    _require_cloud_llm_consent(
        svc,
        allowed=bool(getattr(args, "allow_cloud_llm", False)),
        tenant=scope.tenant_id,
        workspace=scope.workspace_id,
        project=scope.project_id,
    )
    pack = svc.explore(scope, args.query, top_k=int(args.top_k))
    print_json(pack)
    return 0


def cmd_graph_hybrid(args: argparse.Namespace) -> int:
    svc = _graph_service()
    scope = _graph_scope(args)
    _require_cloud_llm_consent(
        svc,
        allowed=bool(getattr(args, "allow_cloud_llm", False)),
        tenant=scope.tenant_id,
        workspace=scope.workspace_id,
        project=scope.project_id,
    )
    print_json(svc.hybrid_search(scope, args.query, top_k=int(args.top_k)))
    return 0


def cmd_graph_generation_context(args: argparse.Namespace) -> int:
    """Operator read path for hybrid_documentation on a seed symbol."""
    svc = _graph_service()
    scope = _graph_scope(args)
    symbol_id = str(getattr(args, "symbol_id", "") or "").strip()
    qn = str(getattr(args, "qualified_name", "") or "").strip()
    if not symbol_id and qn:
        hit = svc.store.get_symbol_by_qualified_name(scope, qn)
        if hit is None:
            matches = [
                symbol
                for symbol in svc.store.list_symbols(scope)
                if symbol.name == qn or symbol.qualified_name.endswith(f".{qn}")
            ]
            if len(matches) == 1:
                hit = matches[0]
            elif len(matches) > 1:
                options = ", ".join(sorted(symbol.qualified_name for symbol in matches[:8]))
                raise SystemExit(
                    f"error: qualified_name is ambiguous: {qn}; use one of: {options}"
                )
        if hit is None:
            raise SystemExit(f"error: qualified_name not found: {qn}")
        symbol_id = hit.id
    if not symbol_id:
        raise SystemExit("error: pass --symbol-id or --qualified-name")
    max_symbols = max(1, min(int(getattr(args, "max_symbols", 12) or 12), 64))
    pack = svc.build_generation_context(scope, symbol_id, max_symbols=max_symbols)
    print_json(pack)
    return 0


def cmd_graph_smoke(args: argparse.Namespace) -> int:
    """One-shot connect proxy: ingest → freshness → hybrid → explore (same process)."""
    svc = _graph_service()
    scope = _graph_scope(args)
    root_path = Path(args.path).resolve()
    if not root_path.is_dir():
        raise SystemExit(f"error: path is not a directory: {root_path}")
    _require_cloud_llm_consent(
        svc,
        allowed=bool(getattr(args, "allow_cloud_llm", False)),
        tenant=scope.tenant_id,
        workspace=scope.workspace_id,
        project=scope.project_id,
        paths=[root_path],
    )
    ingest = svc.ingest_repo(
        scope,
        "cli-smoke",
        f"smoke-{now_iso()}",
        f"smoke-repo:{root_path}",
        {
            "root_path": str(root_path),
            "include_extensions": [".py"],
            "max_files": resolve_discovery_max_files(getattr(args, "max_files", 0)),
            "include_outcomes": True,
        },
    )
    ingest_payload = ingest.to_dict() if hasattr(ingest, "to_dict") else ingest
    fresh = svc.freshness_status(scope)
    hybrid = svc.hybrid_search(scope, args.query, top_k=5)
    explore = svc.explore(scope, args.query, top_k=8)
    report = {
        "ok": bool(hybrid.get("hits")) and bool(explore.get("sections")),
        "ingest": ingest_payload,
        "freshness": fresh,
        "hybrid_hits": len(hybrid.get("hits") or []),
        "embedding_backend": hybrid.get("embedding_backend"),
        "explore_sections": len(explore.get("sections") or []),
        "query": args.query,
    }
    print_json(report)
    return 0 if report["ok"] else 1


def cmd_graph_watch(args: argparse.Namespace) -> int:
    """Poll filesystem and batch pending-sync (debounce; never per keystroke)."""
    script = (
        repo_root()
        / "backend"
        / "services"
        / "code-graph-service"
        / "scripts"
        / "watch_pending_sync.py"
    )
    if not script.is_file():
        raise SystemExit(f"error: watcher script missing: {script}")
    cmd = [
        sys.executable,
        str(script),
        "--path",
        str(Path(args.path).resolve()),
        "--interval",
        str(args.interval),
        "--debounce",
        str(args.debounce),
        "--max-wait",
        str(args.max_wait),
    ]
    if args.once:
        cmd.append("--once")
    env = os.environ.copy()
    env.setdefault("ASTLOOM_TENANT_ID", str(args.tenant))
    env.setdefault("ASTLOOM_WORKSPACE_ID", str(args.workspace))
    env.setdefault("ASTLOOM_PROJECT_ID", str(args.project))
    return subprocess.call(cmd, env=env, cwd=str(repo_root()))
