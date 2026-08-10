"""``astloom upgrade`` — server, client, and control-plane upgrade."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from astloom_cli.upgrade import (
    CONTRACT_VERSION,
    PRODUCT_VERSION,
    UpgradeError,
    check_compatibility,
    create_upgrade_plan,
    finalize_upgrade_job,
    load_upgrade_job,
    prepare_upgrade_job,
    rollback_upgrade_job,
    run_client_upgrade,
    run_upgrade_job,
    server_version_payload,
)
from astloom_cli.upgrade.versions import client_version_payload
from astloom_cli.util import print_json, repo_root


def cmd_upgrade_check(args: argparse.Namespace) -> int:
    client = client_version_payload()
    server: dict[str, str]
    ping_path = str(getattr(args, "from_ping", "") or "").strip()
    if ping_path:
        data = json.loads(Path(ping_path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit("error: --from-ping must be a JSON object")
        server = {
            "product_version": str(data.get("product_version") or ""),
            "contract_version": str(data.get("contract_version") or ""),
            "min_client_contract": str(data.get("min_client_contract") or ""),
        }
    elif getattr(args, "assume_local_server", False):
        server = server_version_payload()
    else:
        server = {
            "product_version": str(getattr(args, "server_product", "") or ""),
            "contract_version": str(getattr(args, "server_contract", "") or ""),
            "min_client_contract": str(getattr(args, "min_client_contract", "") or ""),
        }
        if not server["contract_version"]:
            raise SystemExit(
                "error: provide --from-ping FILE, --assume-local-server, or --server-contract"
            )
    result = check_compatibility(
        client_contract=str(client["contract_version"]),
        server_contract=server["contract_version"],
        min_client_contract=server.get("min_client_contract") or "",
        client_product=str(client["product_version"]),
        server_product=server.get("product_version") or "",
    )
    print_json({"client": client, "server": server, "compatibility": result.to_dict()})
    return 0 if result.ok else 2


def cmd_upgrade_plan(args: argparse.Namespace) -> int:
    plan = create_upgrade_plan(
        root=repo_root(),
        target_product=str(getattr(args, "target", "") or ""),
        mode=str(args.mode),
        risk_level=str(args.risk_level),
    )
    print_json(plan)
    return 0 if plan["compatibility"]["ok"] else 2


def cmd_upgrade_prepare(args: argparse.Namespace) -> int:
    try:
        job = prepare_upgrade_job(
            root=repo_root(),
            mode=str(args.mode),
            risk_level=str(args.risk_level),
            target_product=str(getattr(args, "target", "") or ""),
            actor=str(getattr(args, "actor", "") or "cli"),
            tenant_id=str(getattr(args, "tenant", "") or "astloom"),
            workspace_id=str(getattr(args, "workspace", "") or "dev"),
            project_id=str(getattr(args, "project", "") or "astloom"),
            enqueue_approval=not bool(getattr(args, "no_approval", False)),
        )
    except UpgradeError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print_json(job)
    return 0


def cmd_upgrade_run(args: argparse.Namespace) -> int:
    root = repo_root()
    job_id = str(getattr(args, "job_id", "") or "").strip()
    try:
        if not job_id:
            job = prepare_upgrade_job(
                root=root,
                mode=str(args.mode),
                risk_level=str(args.risk_level),
                target_product=str(getattr(args, "target", "") or ""),
                actor=str(getattr(args, "actor", "") or "cli"),
                tenant_id=str(getattr(args, "tenant", "") or "astloom"),
                workspace_id=str(getattr(args, "workspace", "") or "dev"),
                project_id=str(getattr(args, "project", "") or "astloom"),
                enqueue_approval=not bool(getattr(args, "no_approval", False)),
            )
            job_id = str(job["id"])
        result = run_upgrade_job(
            job_id,
            root=root,
            yes=bool(getattr(args, "yes", False)),
            skip_deploy=bool(getattr(args, "skip_deploy", False)),
        )
    except UpgradeError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print_json(result)
    return 0 if result.get("status") == "succeeded" else 1


def cmd_upgrade_status(args: argparse.Namespace) -> int:
    try:
        job = load_upgrade_job(str(args.job_id), root=repo_root())
    except UpgradeError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print_json(job)
    return 0


def cmd_upgrade_rollback(args: argparse.Namespace) -> int:
    try:
        job = rollback_upgrade_job(str(args.job_id), root=repo_root())
    except UpgradeError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print_json(job)
    return 0


def cmd_upgrade_finalize(args: argparse.Namespace) -> int:
    try:
        result = finalize_upgrade_job(
            str(getattr(args, "job_id", "") or "").strip() or None,
            root=repo_root(),
            runtime=str(getattr(args, "runtime", "") or ""),
        )
    except UpgradeError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print_json(result)
    return 0


def cmd_upgrade_client(args: argparse.Namespace) -> int:
    server = None
    ping_path = str(getattr(args, "from_ping", "") or "").strip()
    if ping_path:
        data = json.loads(Path(ping_path).read_text(encoding="utf-8"))
        server = {
            "product_version": str(data.get("product_version") or ""),
            "contract_version": str(data.get("contract_version") or ""),
            "min_client_contract": str(data.get("min_client_contract") or ""),
        }
    try:
        result = run_client_upgrade(
            root=repo_root(),
            project_dir=Path(str(args.project_dir)).resolve() if args.project_dir else Path.cwd(),
            server_versions=server,
            refresh_venv=not bool(getattr(args, "skip_venv", False)),
            rewire_connect=not bool(getattr(args, "skip_connect", False)),
        )
    except UpgradeError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print_json(result)
    from astloom_cli.client_next_steps import print_client_connect_next_steps

    print_client_connect_next_steps(heading="Next — Usage Profile id (after client upgrade)")
    return 0


def cmd_upgrade_versions(_: argparse.Namespace) -> int:
    print_json(
        {
            "client": client_version_payload(),
            "server_advertisement": server_version_payload(),
            "product_version": PRODUCT_VERSION,
            "contract_version": CONTRACT_VERSION,
        }
    )
    return 0
