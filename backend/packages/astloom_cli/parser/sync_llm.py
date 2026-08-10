"""``connect``, ``sync``, ``llm``, ``purge``."""

from __future__ import annotations

import argparse

from astloom_cli.parser._core import DEFAULT_SYNC_MAX_FILES
from astloom_cli.util import add_scope_args


def register_connect(sub: argparse._SubParsersAction) -> None:
    connect = sub.add_parser(
        "connect",
        help="One-command coding-agent onboarding (interactive HTTPS wizard or connect.yaml)",
    )
    connect.add_argument(
        "connect_mode",
        nargs="?",
        default="",
        metavar="edit|init|PATH[,PATH…]",
        help=(
            "Optional: edit (re-auth HTTPS), init (connect.yaml template), "
            "or one/more project dirs comma-separated (default: cwd). "
            "Each dir is wired for MCP and pinned for sync."
        ),
    )
    connect.add_argument("--config", default="", help="Path to connect.yaml / connect.json")
    connect.add_argument("--project", default="", help="Override project id (default: cwd directory name)")
    connect.add_argument("--server", default="", help="Override server.url (HTTPS API bootstrap)")
    connect.add_argument("--clients", default="", help="Override clients (all or comma-separated ids)")
    connect.add_argument(
        "--include-user-clients",
        action="store_true",
        help="Also write user-global MCP configs",
    )
    connect.add_argument("--dry-run", action="store_true", help="Print MCP fragment only")
    connect.add_argument(
        "--local",
        action="store_true",
        help="Same-host stdio MCP (dogfood this checkout; no HTTPS required)",
    )
    connect.add_argument("--tenant", default="", help="Override scope.tenant (local mode)")
    connect.add_argument("--workspace", default="", help="Override scope.workspace (local mode)")
    connect.add_argument(
        "--usage-profile",
        default="",
        help="Usage Profile id (chosen at connect; required if not in connect.yaml / non-interactive)",
    )
    connect.add_argument(
        "--remote-root",
        default="",
        help="Astloom checkout root (local mode; default: detected repo root / cwd)",
    )


def register_sync(sub: argparse._SubParsersAction) -> None:
    sync = sub.add_parser(
        "sync",
        help=(
            "Sync code into the project graph (auto full vs incremental); "
            "word heal = full-project embedding refresh"
        ),
    )
    add_scope_args(sync, required=False)
    sync.add_argument(
        "--path",
        action="append",
        default=None,
        help="Override: sync only these roots (repeatable). Default: paths from init / paths list",
    )
    sync.set_defaults(max_files=DEFAULT_SYNC_MAX_FILES, sync_mode="", sync_job_id="")
    sync.epilog = (
        "Words: heal (full-project embedding heal after incremental file pass); "
        "jobs [job_id] (server-only: list/detail live client ingest-push jobs); "
        "max-file <n> (aliases: --max-files / --max-file; omit = auto full tree up to "
        "20000, HTTP-batched). "
        "Examples: astloom sync | astloom sync heal | astloom sync jobs | "
        "astloom sync max-file 50"
    )
    sync.add_argument(
        "--json",
        action="store_true",
        help="JSON output (used by sync jobs list/detail)",
    )
    sync.add_argument(
        "--cpu-percent",
        default=None,
        metavar="N",
        help=(
            "Target host CPU share for sync (1-100 or 'auto'). "
            "Derives file workers, local-embed concurrency, and Torch/OMP threads. "
            "Overrides ASTLOOM_SYNC_CPU_PERCENT for this run. "
            "Default: env ASTLOOM_SYNC_CPU_PERCENT or auto"
        ),
    )
    sync.add_argument(
        "--progress-interval",
        type=float,
        default=30.0,
        help="Seconds between progress lines (ETA adapts from observed file rate; default 30)",
    )
    sync.add_argument(
        "--allow-cloud-llm",
        action="store_true",
        help=(
            "Skip interactive cloud-LLM prompt: treat as explicit per-run consent "
            "to send code-derived prompts through a non-local LLM route"
        ),
    )
    sync.add_argument(
        "--skip-nonconforming",
        action="store_true",
        help=(
            "Skip syncing paths that fail Full-tier docs-standards "
            "(no interactive prompt; for scripts). "
            "Conflicts with --sync-nonconforming"
        ),
    )
    sync.add_argument(
        "--sync-nonconforming",
        action="store_true",
        help=(
            "Sync nonconforming docs/code anyway "
            "(skip the interactive standards gate). "
            "Conflicts with --skip-nonconforming"
        ),
    )
    sync.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Extra exclude (dir name or wildcard glob; repeatable). Requires astloom.sync.yaml",
    )
    sync.add_argument(
        "--include-path",
        action="append",
        default=[],
        help="Only sync under this prefix/glob (repeatable). Requires astloom.sync.yaml",
    )
    sync.add_argument(
        "--include-ext",
        action="append",
        default=[],
        help="Override include extensions (repeatable, e.g. --include-ext .py)",
    )


def _register_server_only_middle(sub: argparse._SubParsersAction) -> None:
    llm = sub.add_parser("llm", help="LiteLLM gateway (test connectivity, sessions)")
    llm_sub = llm.add_subparsers(dest="llm_command", required=True)
    llm_sub.add_parser(
        "sessions",
        help="Show in-flight and recent RPM sessions (process-local snapshot)",
    )
    llm_test = llm_sub.add_parser(
        "test",
        help="Send a short prompt (default Hi) via configured LiteLLM model",
    )
    llm_test.add_argument(
        "--prompt",
        default="Hi",
        help="User prompt for the one-shot test (default: Hi)",
    )
    llm_test.add_argument(
        "--model",
        default=None,
        help="Override ASTLOOM_LITELLM_DEFAULT_MODEL for this call",
    )

    context = sub.add_parser(
        "context",
        help="Native context compression (measure savings / process stats)",
    )
    context_sub = context.add_subparsers(dest="context_command", required=True)
    measure = context_sub.add_parser(
        "measure",
        help="Compress a sample and report chars saved / percent reduced",
    )
    measure.add_argument("--file", default=None, help="Path to text/JSON file")
    measure.add_argument("--payload", default=None, help="Inline payload string")
    measure.add_argument(
        "--content-type",
        default="auto",
        choices=["auto", "json", "text"],
        help="Compressor route (default: auto)",
    )
    measure.add_argument(
        "--min-chars",
        type=int,
        default=None,
        help="Override ASTLOOM_CONTEXT_COMPRESS_MIN_CHARS for this run",
    )
    measure.add_argument("--json", action="store_true", help="Print JSON report")
    ctx_stats = context_sub.add_parser(
        "stats",
        help="Show process-local compression counters (CLI process only)",
    )
    ctx_stats.add_argument("--json", action="store_true", help="Print JSON report")

    pack = sub.add_parser(
        "pack",
        help="Change-scoped review pack (secret scan + token estimate; not whole-repo dump)",
    )
    pack_sub = pack.add_subparsers(dest="pack_command", required=True)
    review = pack_sub.add_parser(
        "review",
        help="Pack listed or git-changed files with secret scan and optional --token-budget",
    )
    review.add_argument("--root", default=None, help="Repo root (default: Astloom root)")
    review.add_argument("--files", default="", help="Comma-separated relative paths")
    review.add_argument(
        "--stdin",
        action="store_true",
        help="Read relative paths from stdin (one per line)",
    )
    review.add_argument("--from-git", action="store_true", help="Include files from git diff HEAD")
    review.add_argument("--staged", action="store_true", help="Use staged diff file list / diffs")
    review.add_argument("--include-diff", action="store_true", help="Embed unified diffs")
    review.add_argument("--token-budget", type=int, default=None, help="Fail if estimated tokens exceed N")
    review.add_argument(
        "--hotspot-min-tokens",
        type=int,
        default=50,
        help="List files at/above this estimated token count as hotspots (default 50)",
    )
    review.add_argument("--max-file-bytes", type=int, default=200_000)
    review.add_argument(
        "--allow-secrets",
        action="store_true",
        help="Do not fail closed on secret findings (not recommended)",
    )
    review.add_argument("--out", default=None, help="Write markdown pack to path when ok")
    review.add_argument("--json", action="store_true", help="Print JSON summary")


def register_purge(sub: argparse._SubParsersAction) -> None:
    purge = sub.add_parser(
        "purge",
        help="Wipe project graph data only (requires --yes); then run sync to rebuild",
    )
    add_scope_args(purge, required=False)
    purge.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive wipe of symbols/edges for this scope",
    )


def register_ingest_push(sub: argparse._SubParsersAction) -> None:
    push = sub.add_parser(
        "ingest-push",
        help=(
            "Ingest file bodies from stdin JSON (client content-push; "
            "no on-server source tree required)"
        ),
    )
    add_scope_args(push, required=False)
    push.add_argument(
        "--embedding-refresh-mode",
        default="touched",
        choices=("touched", "full"),
        help="Embedding refresh after push (default: touched)",
    )
    hashes = sub.add_parser(
        "file-hashes",
        help="Print FILE path→content-hash map (for client-side skip)",
    )
    add_scope_args(hashes, required=False)


def _register_destroy_and_list(sub: argparse._SubParsersAction) -> None:
    destroy = sub.add_parser(
        "destroy-profile",
        help=(
            "Delete this scope's Astloom profile data (graph, identity, project state, "
            "env/connect pins, MCP entries). Does NOT delete source code. "
            "Requires two different typed confirmations in the terminal"
        ),
    )
    add_scope_args(destroy, required=False)

    list_profiles = sub.add_parser(
        "list-profiles",
        help="List local tenant/workspace/project profiles and show which scope is active",
    )
    list_profiles.add_argument("--json", action="store_true", help="Print JSON only")
    list_profiles.add_argument("--verbose", action="store_true", help="Human table + JSON")


def register(sub: argparse._SubParsersAction) -> None:
    register_connect(sub)
    register_sync(sub)
    register_ingest_push(sub)
    _register_server_only_middle(sub)
    register_purge(sub)
    _register_destroy_and_list(sub)
