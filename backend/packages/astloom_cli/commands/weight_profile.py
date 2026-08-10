"""CLI: WeightProfile governance (GAP-006)."""

from __future__ import annotations

import argparse

import astloom_cli.state as state
from astloom_cli.util import now_iso, print_json, repo_root, require_scope


def _gov_root():
    return state.default_state_root(repo_root()).parent


def cmd_weight_profile_list(_: argparse.Namespace) -> int:
    from weight_profiles import list_profiles, load_profile

    rows = []
    for profile_id in list_profiles():
        profile = load_profile(profile_id)
        rows.append(
            {
                "profile_id": profile_id,
                "version": profile.get("version"),
                "owner": profile.get("owner"),
                "status": profile.get("status"),
                "risk_level": profile.get("risk_level"),
            }
        )
    print_json({"profiles": rows})
    return 0


def cmd_weight_profile_show(args: argparse.Namespace) -> int:
    from weight_profiles import load_profile

    print_json(load_profile(args.profile_id))
    return 0


def cmd_weight_profile_validate(args: argparse.Namespace) -> int:
    from weight_profiles import load_profile, validate_profile

    profile = load_profile(args.profile_id)
    validate_profile(profile)
    print_json({"profile_id": args.profile_id, "valid": True})
    return 0


def cmd_weight_profile_activate(args: argparse.Namespace) -> int:
    from weight_profiles import activate_profile

    tenant, workspace, project = require_scope(args, with_defaults=True)
    root = state.default_state_root(repo_root())
    project_state = state.load_project(root, tenant, workspace, project)
    result = activate_profile(
        _gov_root(),
        args.profile_id,
        actor=str(getattr(args, "actor", "") or "cli"),
        reason=args.reason or "activate",
        now_iso=now_iso(),
        require_approval=not bool(getattr(args, "force", False)),
    )
    if project_state is not None:
        project_state["weight_profile"] = args.profile_id
        state.save_project(root, project_state)
        result["project_updated"] = True
    else:
        result["project_updated"] = False
    print_json(result)
    return 0


def cmd_weight_profile_rollback(args: argparse.Namespace) -> int:
    from weight_profiles import rollback_profile

    tenant, workspace, project = require_scope(args, with_defaults=True)
    root = state.default_state_root(repo_root())
    project_state = state.load_project(root, tenant, workspace, project)
    result = rollback_profile(
        _gov_root(),
        actor=str(getattr(args, "actor", "") or "cli"),
        reason=args.reason or "rollback",
        now_iso=now_iso(),
        steps=int(args.steps or 1),
    )
    if project_state is not None:
        project_state["weight_profile"] = result["active_profile_id"]
        state.save_project(root, project_state)
        result["project_updated"] = True
    else:
        result["project_updated"] = False
    print_json(result)
    return 0


def cmd_weight_profile_active(args: argparse.Namespace) -> int:
    from weight_profiles import get_active_profile_id, load_profile

    tenant, workspace, project = require_scope(args, with_defaults=True)
    root = state.default_state_root(repo_root())
    project_state = state.load_project(root, tenant, workspace, project)
    profile_id = get_active_profile_id(_gov_root(), project_state=project_state)
    print_json({"active_profile_id": profile_id, "profile": load_profile(profile_id)})
    return 0
