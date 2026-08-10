"""Astloom CLI entry point — parse args and dispatch to command modules."""

from __future__ import annotations

from astloom_cli.util import ensure_service_import_paths, repo_root

ensure_service_import_paths()

from astloom_cli.commands.connect import cmd_connect
from astloom_cli.commands.client import cmd_client_list_mcp_clients
from astloom_cli.commands.cursor import cmd_cursor_export
from astloom_cli.commands.doctor import cmd_doctor, cmd_version
from astloom_cli.commands.init_cmd import cmd_init
from astloom_cli.commands.paths_cmd import cmd_paths_add, cmd_paths_list, cmd_paths_remove
from astloom_cli.commands.status import cmd_status
from astloom_cli.commands.inventory import cmd_inventory
from astloom_cli.commands.docs_standards import cmd_docs_standards
from astloom_cli.commands.docs_suggest_links import cmd_docs_suggest_links
from astloom_cli.commands.docs_catalog import cmd_docs_catalog
from astloom_cli.commands.quality_audit import cmd_quality_audit
from astloom_cli.commands.stats import cmd_stats
from astloom_cli.commands.destroy_cmd import cmd_destroy_profile
from astloom_cli.commands.list_profiles import cmd_list_profiles
from astloom_cli.commands.sync import cmd_purge, cmd_sync
from astloom_cli.commands.ingest_push import cmd_file_hashes, cmd_ingest_push
from astloom_cli.commands.llm_cmd import cmd_llm_sessions, cmd_llm_test
from astloom_cli.commands.context_cmd import cmd_context_measure, cmd_context_stats
from astloom_cli.commands.pack_cmd import cmd_pack_review
from astloom_cli.commands.graph import (
    cmd_graph_explore,
    cmd_graph_freshness,
    cmd_graph_generation_context,
    cmd_graph_hybrid,
    cmd_graph_ingest,
    cmd_graph_smoke,
    cmd_graph_watch,
)
from astloom_cli.commands.mcp_cmd import (
    cmd_mcp_serve,
    cmd_mcp_serve_http,
    cmd_mcp_tokens,
    cmd_mcp_tools,
)
from astloom_cli.commands.path_cmd import cmd_path_install
from astloom_cli.commands.ports import cmd_ports_check, cmd_ports_show
from astloom_cli.commands.approval import (
    cmd_approval_accept,
    cmd_approval_enqueue,
    cmd_approval_mode_set,
    cmd_approval_mode_show,
    cmd_approval_queue,
    cmd_approval_reject,
    cmd_approval_show,
)
from astloom_cli.commands.followup_tasks import (
    cmd_followup_tasks_adopt_legacy,
    cmd_followup_tasks_list,
    cmd_followup_tasks_purge,
    cmd_followup_tasks_reconcile,
    cmd_followup_tasks_status,
)
from astloom_cli.commands.profile import cmd_profile_list, cmd_profile_show
from astloom_cli.commands.project import (
    cmd_project_activate,
    cmd_project_effective,
    cmd_project_register,
    cmd_project_show,
)
from astloom_cli.commands.weight_profile import (
    cmd_weight_profile_activate,
    cmd_weight_profile_active,
    cmd_weight_profile_list,
    cmd_weight_profile_rollback,
    cmd_weight_profile_show,
    cmd_weight_profile_validate,
)
from astloom_cli.commands.service_cmd import (
    cmd_boot_disable,
    cmd_boot_enable,
    cmd_service_detail,
    cmd_service_restart,
    cmd_service_start,
    cmd_service_status,
    cmd_service_stop,
)
from astloom_cli.commands.upgrade import (
    cmd_upgrade_check,
    cmd_upgrade_client,
    cmd_upgrade_finalize,
    cmd_upgrade_plan,
    cmd_upgrade_prepare,
    cmd_upgrade_rollback,
    cmd_upgrade_run,
    cmd_upgrade_status,
    cmd_upgrade_versions,
)
from astloom_cli.commands.backup_cmd import (
    cmd_backup_dry_run,
    cmd_backup_export,
    cmd_backup_restore,
    cmd_backup_status,
    cmd_backup_validate,
)
from astloom_cli.parser import build_parser

__all__ = ["build_parser", "main", "repo_root"]


def main(argv: list[str] | None = None) -> int:
    try:
        return _dispatch(argv)
    except KeyboardInterrupt:
        print("\nInterrupted — check: astloom service status", flush=True)
        return 130


def _dispatch(argv: list[str] | None = None) -> int:
    from astloom_cli.client_allowlist import client_command_allowed, deny_message_for_client_role
    from astloom_cli.service_runtime.paths import install_role

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version and not args.command:
        return cmd_version(args)
    if not args.command:
        parser.print_help()
        return 2

    # Defense in depth: client-only hosts must not run server-admin via full module.
    if install_role(repo_root()) == "client" and not client_command_allowed(args.command, args):
        print(deny_message_for_client_role(args.command), flush=True)
        return 2

    if args.command == "version":
        return cmd_version(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "service":
        if args.service_command == "start":
            return cmd_service_start(args)
        if args.service_command == "stop":
            return cmd_service_stop(args)
        if args.service_command == "restart":
            return cmd_service_restart(args)
        if args.service_command == "status":
            return cmd_service_status(args)
        if args.service_command == "detail":
            return cmd_service_detail(args)
    if args.command == "boot":
        if args.boot_command == "enable":
            return cmd_boot_enable(args)
        if args.boot_command == "disable":
            return cmd_boot_disable(args)
    if args.command == "init":
        return cmd_init(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "inventory":
        return cmd_inventory(args)
    if args.command == "docs-standards":
        return cmd_docs_standards(args)
    if args.command == "docs-suggest-links":
        return cmd_docs_suggest_links(args)
    if args.command == "docs-catalog":
        return cmd_docs_catalog(args)
    if args.command == "quality-audit":
        return cmd_quality_audit(args)
    if args.command == "stats":
        return cmd_stats(args)
    if args.command == "connect":
        return cmd_connect(args)
    if args.command == "sync":
        return cmd_sync(args)
    if args.command == "ingest-push":
        return cmd_ingest_push(args)
    if args.command == "file-hashes":
        return cmd_file_hashes(args)
    if args.command == "llm":
        if args.llm_command == "sessions":
            return cmd_llm_sessions(args)
        if args.llm_command == "test":
            return cmd_llm_test(args)
    if args.command == "context":
        if args.context_command == "measure":
            return cmd_context_measure(args)
        if args.context_command == "stats":
            return cmd_context_stats(args)
    if args.command == "pack":
        if args.pack_command == "review":
            return cmd_pack_review(args)
    if args.command == "purge":
        return cmd_purge(args)
    if args.command == "destroy-profile":
        return cmd_destroy_profile(args)
    if args.command == "list-profiles":
        return cmd_list_profiles(args)
    if args.command == "paths":
        if args.paths_command == "list":
            return cmd_paths_list(args)
        if args.paths_command == "add":
            return cmd_paths_add(args)
        if args.paths_command == "remove":
            return cmd_paths_remove(args)
    if args.command == "profile":
        if args.profile_command in (None, "list"):
            return cmd_profile_list(args)
        if args.profile_command == "show":
            return cmd_profile_show(args)
    if args.command == "project":
        if args.project_command == "register":
            return cmd_project_register(args)
        if args.project_command == "activate":
            return cmd_project_activate(args)
        if args.project_command == "show":
            return cmd_project_show(args)
        if args.project_command == "effective":
            return cmd_project_effective(args)
    if args.command == "cursor":
        if args.cursor_command == "export":
            return cmd_cursor_export(args)
    if args.command == "client":
        if args.client_command == "list-mcp-clients":
            return cmd_client_list_mcp_clients(args)
    if args.command == "mcp":
        if args.mcp_command == "tools":
            return cmd_mcp_tools(args)
        if args.mcp_command == "tokens":
            return cmd_mcp_tokens(args)
        if args.mcp_command == "serve":
            return cmd_mcp_serve(args)
        if args.mcp_command == "serve-http":
            return cmd_mcp_serve_http(args)
    if args.command == "path":
        if args.path_command == "install":
            return cmd_path_install(args)
    if args.command == "ports":
        if args.ports_command == "show":
            return cmd_ports_show(args)
        if args.ports_command == "check":
            return cmd_ports_check(args)
    if args.command == "graph":
        if args.graph_command == "ingest":
            return cmd_graph_ingest(args)
        if args.graph_command == "freshness":
            return cmd_graph_freshness(args)
        if args.graph_command == "explore":
            return cmd_graph_explore(args)
        if args.graph_command == "hybrid":
            return cmd_graph_hybrid(args)
        if args.graph_command == "generation-context":
            return cmd_graph_generation_context(args)
        if args.graph_command == "smoke":
            return cmd_graph_smoke(args)
        if args.graph_command == "watch":
            return cmd_graph_watch(args)
    if args.command == "followup-tasks":
        if args.followup_tasks_command == "list":
            return cmd_followup_tasks_list(args)
        if args.followup_tasks_command == "status":
            return cmd_followup_tasks_status(args)
        if args.followup_tasks_command == "adopt-legacy":
            return cmd_followup_tasks_adopt_legacy(args)
        if args.followup_tasks_command == "reconcile":
            return cmd_followup_tasks_reconcile(args)
        if args.followup_tasks_command == "purge":
            return cmd_followup_tasks_purge(args)
    if args.command == "approval":
        if args.approval_command == "mode":
            if args.approval_mode_command == "show":
                return cmd_approval_mode_show(args)
            if args.approval_mode_command == "set":
                return cmd_approval_mode_set(args)
        if args.approval_command == "queue":
            return cmd_approval_queue(args)
        if args.approval_command == "show":
            return cmd_approval_show(args)
        if args.approval_command == "enqueue":
            return cmd_approval_enqueue(args)
        if args.approval_command == "accept":
            return cmd_approval_accept(args)
        if args.approval_command == "reject":
            return cmd_approval_reject(args)
    if args.command == "weight-profile":
        if args.weight_profile_command == "list":
            return cmd_weight_profile_list(args)
        if args.weight_profile_command == "show":
            return cmd_weight_profile_show(args)
        if args.weight_profile_command == "validate":
            return cmd_weight_profile_validate(args)
        if args.weight_profile_command == "active":
            return cmd_weight_profile_active(args)
        if args.weight_profile_command == "activate":
            return cmd_weight_profile_activate(args)
        if args.weight_profile_command == "rollback":
            return cmd_weight_profile_rollback(args)
    if args.command == "upgrade":
        if args.upgrade_command == "versions":
            return cmd_upgrade_versions(args)
        if args.upgrade_command == "check":
            return cmd_upgrade_check(args)
        if args.upgrade_command == "plan":
            return cmd_upgrade_plan(args)
        if args.upgrade_command == "prepare":
            return cmd_upgrade_prepare(args)
        if args.upgrade_command == "run":
            return cmd_upgrade_run(args)
        if args.upgrade_command == "status":
            return cmd_upgrade_status(args)
        if args.upgrade_command == "rollback":
            return cmd_upgrade_rollback(args)
        if args.upgrade_command == "finalize":
            return cmd_upgrade_finalize(args)
        if args.upgrade_command == "client":
            return cmd_upgrade_client(args)
    if args.command == "backup":
        if args.backup_command == "export":
            return cmd_backup_export(args)
        if args.backup_command == "validate":
            return cmd_backup_validate(args)
        if args.backup_command == "restore":
            return cmd_backup_restore(args)
        if args.backup_command == "dry-run":
            return cmd_backup_dry_run(args)
        if args.backup_command == "status":
            return cmd_backup_status(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
