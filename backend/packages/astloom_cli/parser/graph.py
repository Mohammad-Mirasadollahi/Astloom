"""``graph`` subcommands."""

from __future__ import annotations

import argparse

from astloom_cli.util import add_scope_args


def register(sub: argparse._SubParsersAction) -> None:
    graph = sub.add_parser("graph", help="Code-graph operator smoke (ingest / freshness / explore / hybrid)")
    graph_sub = graph.add_subparsers(dest="graph_command", required=True)

    gin = graph_sub.add_parser("ingest", help="Ingest a repository root into the code graph")
    add_scope_args(gin)
    gin.add_argument("--path", required=True, help="Repository or source root to ingest")
    gin.add_argument("--max-files", type=int, default=200)
    gin.add_argument("--allow-cloud-llm", action="store_true")

    gfr = graph_sub.add_parser("freshness", help="Show freshness / pending-sync status")
    add_scope_args(gfr)
    gfr.add_argument("--mark-pending", default="", help="Optional file path to mark pending")

    gex = graph_sub.add_parser("explore", help="Run explore pack for a query")
    add_scope_args(gex)
    gex.add_argument("--query", required=True)
    gex.add_argument("--top-k", type=int, default=12)
    gex.add_argument("--allow-cloud-llm", action="store_true")

    ghy = graph_sub.add_parser("hybrid", help="Run hybrid search")
    add_scope_args(ghy)
    ghy.add_argument("--query", required=True)
    ghy.add_argument("--top-k", type=int, default=10)
    ghy.add_argument("--allow-cloud-llm", action="store_true")

    ggc = graph_sub.add_parser(
        "generation-context",
        help="Build generation context pack (includes hybrid_documentation layers)",
    )
    add_scope_args(ggc)
    ggc.add_argument("--symbol-id", default="", help="Seed symbol id")
    ggc.add_argument("--qualified-name", default="", help="Seed qualified_name (if no --symbol-id)")
    ggc.add_argument("--max-symbols", type=int, default=12)

    gsm = graph_sub.add_parser("smoke", help="Ingest + freshness + hybrid + explore in one process")
    add_scope_args(gsm)
    gsm.add_argument("--path", required=True)
    gsm.add_argument("--query", default="login password")
    gsm.add_argument("--max-files", type=int, default=50)
    gsm.add_argument("--allow-cloud-llm", action="store_true")

    gwa = graph_sub.add_parser(
        "watch",
        help="Batched poll sidecar for pending-sync (debounce; not per-edit / not continuous index)",
    )
    add_scope_args(gwa)
    gwa.add_argument("--path", required=True)
    gwa.add_argument("--interval", type=float, default=2.0, help="Poll interval seconds")
    gwa.add_argument(
        "--debounce",
        type=float,
        default=30.0,
        help="Quiet seconds before flushing a change batch (agent-coding safe)",
    )
    gwa.add_argument(
        "--max-wait",
        type=float,
        default=120.0,
        help="Max seconds to hold a batch while files keep changing",
    )
    gwa.add_argument("--once", action="store_true", help="Single poll cycle then exit")
