"""``approval``, ``weight-profile``, and ``followup-tasks`` CLI parsers."""

from __future__ import annotations

import argparse

from astloom_cli.util import add_scope_args


def register(sub: argparse._SubParsersAction) -> None:
    followup = sub.add_parser(
        "followup-tasks",
        help="List / reconcile / purge automated follow-up Tasks (sync + quality)",
    )
    followup_sub = followup.add_subparsers(dest="followup_tasks_command", required=True)

    ft_list = followup_sub.add_parser("list", help="List automated follow-up Tasks")
    add_scope_args(ft_list, required=False)
    ft_list.add_argument(
        "--origin",
        default="all",
        help="all | sync-followup (sync) | mcp-quality (quality)",
    )
    ft_list.add_argument(
        "--status",
        default="all",
        help="all | open | terminal",
    )

    ft_adopt = followup_sub.add_parser(
        "adopt-legacy",
        help="Stamp retention metadata onto pre-lifecycle Quality: Tasks + cancel dupes",
    )
    add_scope_args(ft_adopt, required=False)
    ft_adopt.add_argument("--actor", default="astloom-cli-followup")
    ft_adopt.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview adopt/cancel without writing",
    )
    ft_adopt.add_argument(
        "--yes",
        action="store_true",
        help="Confirm adopt (required unless --dry-run)",
    )

    ft_status = followup_sub.add_parser(
        "status",
        help="Summary counts + stale open fingerprints vs current debt",
    )
    add_scope_args(ft_status, required=False)
    ft_status.add_argument(
        "--origin",
        default="all",
        help="all | sync-followup (sync) | mcp-quality (quality)",
    )

    ft_recon = followup_sub.add_parser(
        "reconcile",
        help="Cancel open automated Tasks whose fingerprint is no longer active",
    )
    add_scope_args(ft_recon, required=False)
    ft_recon.add_argument(
        "--origin",
        default="all",
        help="all | sync-followup (sync) | mcp-quality (quality)",
    )
    ft_recon.add_argument("--actor", default="astloom-cli-followup")
    ft_recon.add_argument(
        "--dry-run",
        action="store_true",
        help="Show would-cancel list without transitioning",
    )

    ft_purge = followup_sub.add_parser(
        "purge",
        help="Hard-delete terminal automated Tasks older than retention days",
    )
    add_scope_args(ft_purge, required=False)
    ft_purge.add_argument(
        "--days",
        type=int,
        default=None,
        help="Override ASTLOOM_FOLLOWUP_TASK_RETENTION_DAYS (default from env / 30)",
    )
    ft_purge.add_argument("--actor", default="astloom-cli-followup")
    ft_purge.add_argument(
        "--dry-run",
        action="store_true",
        help="Show would-purge list without deleting",
    )
    ft_purge.add_argument(
        "--yes",
        action="store_true",
        help="Confirm hard-delete (required unless --dry-run)",
    )

    approval = sub.add_parser("approval", help="Human Accept queue + ApprovalMode (GAP-004)")
    approval_sub = approval.add_subparsers(dest="approval_command", required=True)

    mode = approval_sub.add_parser("mode", help="Show or set ApprovalMode")
    mode_sub = mode.add_subparsers(dest="approval_mode_command", required=True)
    show = mode_sub.add_parser("show", help="Show effective ApprovalModeProfile")
    add_scope_args(show, required=False)
    set_p = mode_sub.add_parser("set", help="Set project ApprovalMode")
    add_scope_args(set_p, required=False)
    set_p.add_argument("mode", choices=["manual", "auto_approve", "system_routed"])
    set_p.add_argument("--actor", default="cli")

    queue = approval_sub.add_parser("queue", help="List / track Accept gates (filter by id/time/status)")
    add_scope_args(queue, required=False)
    queue.add_argument("--all", action="store_true", help="Include resolved items")
    queue.add_argument("--id", default="", help="Filter by approval id")
    queue.add_argument("--subject-ref", default="", help="Filter by subject_ref")
    queue.add_argument(
        "--status",
        default="",
        help="Filter by status: pending, approved, rejected (implies history)",
    )
    queue.add_argument(
        "--since",
        "-s",
        default="",
        help="Created at/after: 24h, 7d, 30d, or ISO",
    )
    queue.add_argument("--until", "-u", default="", help="Created at/before: ISO")

    show_gate = approval_sub.add_parser("show", help="Show one Accept gate by id")
    add_scope_args(show_gate, required=False)
    show_gate.add_argument("approval_id")

    enqueue = approval_sub.add_parser("enqueue", help="Open an Accept gate (CLI surface)")
    add_scope_args(enqueue, required=False)
    enqueue.add_argument("--subject-ref", required=True)
    enqueue.add_argument("--subject-class", default="")
    enqueue.add_argument("--risk-level", default="medium", choices=["low", "medium", "high", "critical"])
    enqueue.add_argument("--reason", default="")
    enqueue.add_argument("--actor", default="cli")

    accept = approval_sub.add_parser("accept", help="Accept a pending gate")
    add_scope_args(accept, required=False)
    accept.add_argument("approval_id")
    accept.add_argument("--reason", default="accepted")
    accept.add_argument("--actor", default="cli")

    reject = approval_sub.add_parser("reject", help="Reject a pending gate")
    add_scope_args(reject, required=False)
    reject.add_argument("approval_id")
    reject.add_argument("--reason", default="rejected")
    reject.add_argument("--actor", default="cli")

    weight = sub.add_parser("weight-profile", help="WeightProfile governance (GAP-006)")
    weight_sub = weight.add_subparsers(dest="weight_profile_command", required=True)
    weight_sub.add_parser("list", help="List catalog WeightProfiles")
    show_w = weight_sub.add_parser("show", help="Show one WeightProfile JSON")
    show_w.add_argument("profile_id")
    val = weight_sub.add_parser("validate", help="Validate one WeightProfile")
    val.add_argument("profile_id")
    active = weight_sub.add_parser("active", help="Show active WeightProfile")
    add_scope_args(active, required=False)
    act = weight_sub.add_parser("activate", help="Activate a WeightProfile")
    add_scope_args(act, required=False)
    act.add_argument("profile_id")
    act.add_argument("--actor", default="cli")
    act.add_argument("--reason", default="activate")
    act.add_argument("--force", action="store_true", help="Skip approved_by check")
    rb = weight_sub.add_parser("rollback", help="Roll back to previous activation")
    add_scope_args(rb, required=False)
    rb.add_argument("--steps", type=int, default=1)
    rb.add_argument("--actor", default="cli")
    rb.add_argument("--reason", default="rollback")
