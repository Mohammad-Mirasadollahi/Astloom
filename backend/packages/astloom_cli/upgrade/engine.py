"""
Upgrade control plane for Astloom server and coding-agent clients.

Role: plan / backup / approve / run / evidence / rollback for local and
control-plane upgrade jobs.
Source of truth: ``.astloom/upgrade-jobs/<id>.json`` plus stamped
``install-state.env`` product/contract versions after success.
Fail closed on incompatible MCP contracts and missing approval for
high-risk control-plane runs; fail open when optional remote ping is
unreachable (report advisory, do not block local server upgrade).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from astloom_cli.upgrade.compat import check_compatibility
from astloom_cli.upgrade.versions import (
    CONTRACT_VERSION,
    PRODUCT_VERSION,
    client_version_payload,
    parse_install_state_kv,
    stamp_install_versions,
)
from astloom_cli.util import now_iso, repo_root

UPGRADE_STEPS = (
    "read_state",
    "compare_versions",
    "validate_compatibility",
    "validate_config",
    "create_plan",
    "request_approval",
    "backup",
    "deploy",
    "smoke",
    "update_registry",
    "evidence",
)


class UpgradeError(RuntimeError):
    """Fail-closed upgrade error."""


@dataclass
class UpgradePaths:
    root: Path

    @property
    def astloom_dir(self) -> Path:
        return self.root / ".astloom"

    @property
    def jobs_dir(self) -> Path:
        return self.astloom_dir / "upgrade-jobs"

    @property
    def backups_dir(self) -> Path:
        return self.astloom_dir / "upgrade-backups"

    @property
    def install_state(self) -> Path:
        return self.astloom_dir / "install-state.env"

    def job_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"


def _paths(root: Path | None = None) -> UpgradePaths:
    return UpgradePaths(root=(root or repo_root()).resolve())


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_upgrade_job(job_id: str, *, root: Path | None = None) -> dict[str, Any]:
    paths = _paths(root)
    path = paths.job_path(job_id)
    if not path.is_file():
        raise UpgradeError(f"upgrade job not found: {job_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise UpgradeError(f"invalid upgrade job: {job_id}")
    return data


def _save_job(job: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    paths = _paths(root)
    job_id = str(job["id"])
    job["updated_at"] = now_iso()
    _atomic_write_json(paths.job_path(job_id), job)
    return job


def _mark_step(job: dict[str, Any], step: str, status: str, detail: str = "") -> None:
    steps = job.setdefault("steps", {})
    steps[step] = {"status": status, "detail": detail, "at": now_iso()}


def create_upgrade_plan(
    *,
    root: Path | None = None,
    target_product: str = "",
    mode: str = "local",
    risk_level: str = "medium",
    server_versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build an upgrade plan from current install state (does not persist a job)."""
    paths = _paths(root)
    state = parse_install_state_kv(paths.root)
    current_product = state.get("product_version") or "unknown"
    current_contract = state.get("contract_version") or CONTRACT_VERSION
    runtime = state.get("runtime") or "host"
    target = (target_product or PRODUCT_VERSION).strip() or PRODUCT_VERSION
    server = server_versions or {
        "product_version": PRODUCT_VERSION,
        "contract_version": CONTRACT_VERSION,
        "min_client_contract": CONTRACT_VERSION,
    }
    compat = check_compatibility(
        client_contract=current_contract,
        server_contract=str(server.get("contract_version") or CONTRACT_VERSION),
        min_client_contract=str(server.get("min_client_contract") or ""),
        client_product=current_product if current_product != "unknown" else PRODUCT_VERSION,
        server_product=str(server.get("product_version") or PRODUCT_VERSION),
    )
    requires_approval = mode == "control-plane" or risk_level in {"high", "critical"}
    return {
        "mode": mode,
        "risk_level": risk_level,
        "requires_approval": requires_approval,
        "runtime": runtime,
        "current": {
            "product_version": current_product,
            "contract_version": current_contract,
            "runtime": runtime,
            "install_state_present": paths.install_state.is_file(),
        },
        "target": {
            "product_version": target,
            "contract_version": CONTRACT_VERSION,
        },
        "compatibility": compat.to_dict(),
        "steps": list(UPGRADE_STEPS),
        "rollback": {
            "strategy": "restore_install_state_from_backup",
            "forward_fix": "re-run astloom upgrade run after fixing blockers",
        },
    }


def prepare_upgrade_job(
    *,
    root: Path | None = None,
    mode: str = "local",
    risk_level: str = "medium",
    target_product: str = "",
    actor: str = "cli",
    tenant_id: str = "astloom",
    workspace_id: str = "dev",
    project_id: str = "astloom",
    enqueue_approval: bool = True,
) -> dict[str, Any]:
    """Create a durable upgrade job and optionally open an Accept gate."""
    paths = _paths(root)
    if not paths.install_state.is_file() and mode != "client":
        raise UpgradeError(
            "no install-state.env — run bash install.sh first (or upgrade --mode client)"
        )
    plan = create_upgrade_plan(
        root=paths.root,
        target_product=target_product,
        mode=mode,
        risk_level=risk_level,
    )
    if not plan["compatibility"]["ok"] and mode != "client":
        raise UpgradeError(plan["compatibility"]["reason"])

    job_id = str(uuid4())
    job: dict[str, Any] = {
        "id": job_id,
        "schema_version": "1",
        "status": "planned",
        "mode": mode,
        "risk_level": risk_level,
        "actor": actor,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "project_id": project_id,
        "plan": plan,
        "approval_id": None,
        "backup_path": None,
        "evidence_path": None,
        "steps": {},
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "error": None,
    }
    for step in ("read_state", "compare_versions", "validate_compatibility", "validate_config", "create_plan"):
        _mark_step(job, step, "ok")

    if plan["requires_approval"] and enqueue_approval:
        from approval_modes import enqueue_gate
        import astloom_cli.state as state

        gate = enqueue_gate(
            state.default_state_root(paths.root),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            project_id=project_id,
            subject_ref=f"upgrade:{job_id}",
            subject_class="platform.upgrade",
            risk_level=risk_level,
            actor=actor,
            reason=f"upgrade {plan['current']['product_version']} → {plan['target']['product_version']}",
            now_iso=now_iso(),
        )
        job["approval_id"] = gate["id"]
        _mark_step(job, "request_approval", "pending", gate["id"])
        if gate["status"] == "approved":
            job["status"] = "approved"
            _mark_step(job, "request_approval", "ok", "auto_approved")
        else:
            job["status"] = "awaiting_approval"
    else:
        _mark_step(job, "request_approval", "skipped", "not required")
        job["status"] = "approved"

    return _save_job(job, root=paths.root)


def _backup(job: dict[str, Any], *, root: Path) -> Path:
    paths = _paths(root)
    dest = paths.backups_dir / str(job["id"])
    dest.mkdir(parents=True, exist_ok=True)
    if paths.install_state.is_file():
        shutil.copy2(paths.install_state, dest / "install-state.env")
    sync = paths.root / "astloom.sync.yaml"
    if sync.is_file():
        shutil.copy2(sync, dest / "astloom.sync.yaml")
    # Record compose env presence without copying secrets.
    compose_env = paths.root / "backend" / "deployments" / "compose" / ".env.local"
    meta = {
        "backed_up_at": now_iso(),
        "compose_env_present": compose_env.is_file(),
        "product_version": PRODUCT_VERSION,
        "contract_version": CONTRACT_VERSION,
    }
    (dest / "backup-meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return dest


def write_evidence_report(job: dict[str, Any], *, root: Path | None = None) -> Path:
    paths = _paths(root)
    reports = paths.astloom_dir / "upgrade-evidence"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / f"{job['id']}.json"
    report = {
        "job_id": job["id"],
        "status": job.get("status"),
        "mode": job.get("mode"),
        "plan": job.get("plan"),
        "steps": job.get("steps"),
        "backup_path": job.get("backup_path"),
        "approval_id": job.get("approval_id"),
        "error": job.get("error"),
        "product_version": PRODUCT_VERSION,
        "contract_version": CONTRACT_VERSION,
        "written_at": now_iso(),
    }
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _run_install_script(root: Path, *, runtime: str) -> None:
    install_sh = root / "install.sh"
    if not install_sh.is_file():
        raise UpgradeError(f"missing install.sh at {install_sh}")
    cmd = [
        "bash",
        str(install_sh),
        "--non-interactive",
        f"--runtime={runtime}",
    ]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise UpgradeError(
            f"install.sh failed ({proc.returncode}): {(proc.stderr or proc.stdout)[-2000:]}"
        )


def _run_doctor(root: Path) -> None:
    cli = root / ".venv" / "bin" / "astloom"
    if not cli.is_file():
        raise UpgradeError("post-upgrade smoke failed: .venv/bin/astloom missing")
    proc = subprocess.run(
        [str(cli), "doctor"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise UpgradeError(f"doctor failed: {(proc.stderr or proc.stdout)[-1500:]}")


def _approval_satisfied(job: dict[str, Any], *, root: Path, force_yes: bool) -> bool:
    if job.get("status") == "approved":
        return True
    if force_yes and job.get("mode") == "local" and job.get("risk_level") not in {"critical"}:
        return True
    approval_id = job.get("approval_id")
    if not approval_id:
        return job.get("status") in {"approved", "planned"} and not job["plan"].get(
            "requires_approval"
        )
    from approval_modes import get_gate
    import astloom_cli.state as state

    gate = get_gate(
        state.default_state_root(root),
        tenant_id=str(job["tenant_id"]),
        workspace_id=str(job["workspace_id"]),
        project_id=str(job["project_id"]),
        approval_id=str(approval_id),
    )
    if gate is None:
        return False
    if gate.get("status") == "approved":
        job["status"] = "approved"
        _mark_step(job, "request_approval", "ok", str(approval_id))
        return True
    return False


def run_upgrade_job(
    job_id: str,
    *,
    root: Path | None = None,
    yes: bool = False,
    skip_deploy: bool = False,
) -> dict[str, Any]:
    """Execute an approved upgrade job (local install path or control-plane)."""
    paths = _paths(root)
    job = load_upgrade_job(job_id, root=paths.root)
    if job.get("mode") == "client":
        raise UpgradeError("use astloom upgrade client for client-mode jobs")

    try:
        if not _approval_satisfied(job, root=paths.root, force_yes=yes):
            raise UpgradeError(
                f"upgrade awaiting approval ({job.get('approval_id')}); "
                "accept the gate or pass --yes for local non-critical"
            )

        backup_path = _backup(job, root=paths.root)
        job["backup_path"] = str(backup_path)
        _mark_step(job, "backup", "ok", str(backup_path))
        job["status"] = "running"
        _save_job(job, root=paths.root)

        runtime = str(job.get("plan", {}).get("runtime") or "host")
        if skip_deploy:
            _mark_step(job, "deploy", "skipped", "skip_deploy")
        else:
            _run_install_script(paths.root, runtime=runtime)
            _mark_step(job, "deploy", "ok", f"install.sh runtime={runtime}")

        _run_doctor(paths.root)
        _mark_step(job, "smoke", "ok", "astloom doctor")

        stamped = stamp_install_versions(paths.root, runtime=runtime)
        _mark_step(job, "update_registry", "ok", stamped.get("path", ""))

        evidence = write_evidence_report(job, root=paths.root)
        job["evidence_path"] = str(evidence)
        _mark_step(job, "evidence", "ok", str(evidence))
        job["status"] = "succeeded"
        job["error"] = None
    except Exception as exc:  # noqa: BLE001 — surface on job record
        job["status"] = "failed"
        job["error"] = str(exc)
        _mark_step(job, "evidence", "error", str(exc))
        evidence = write_evidence_report(job, root=paths.root)
        job["evidence_path"] = str(evidence)
        _save_job(job, root=paths.root)
        raise UpgradeError(str(exc)) from exc

    return _save_job(job, root=paths.root)


def finalize_upgrade_job(
    job_id: str | None = None,
    *,
    root: Path | None = None,
    runtime: str = "",
) -> dict[str, Any]:
    """Stamp versions + evidence after an external ``install.sh --upgrade`` deploy."""
    paths = _paths(root)
    stamped = stamp_install_versions(paths.root, runtime=runtime)
    if job_id:
        job = load_upgrade_job(job_id, root=paths.root)
        _mark_step(job, "deploy", "ok", "external install.sh --upgrade")
        _mark_step(job, "smoke", "ok", "deferred_to_installer_verify")
        _mark_step(job, "update_registry", "ok", stamped.get("path", ""))
        evidence = write_evidence_report(job, root=paths.root)
        job["evidence_path"] = str(evidence)
        _mark_step(job, "evidence", "ok", str(evidence))
        job["status"] = "succeeded"
        return _save_job(job, root=paths.root)
    # No job: write a one-shot evidence blob.
    synthetic = {
        "id": f"install-{now_iso().replace(':', '').replace('-', '')}",
        "status": "succeeded",
        "mode": "local",
        "plan": create_upgrade_plan(root=paths.root, mode="local"),
        "steps": {"update_registry": {"status": "ok", "detail": stamped.get("path", "")}},
        "backup_path": None,
        "approval_id": None,
        "error": None,
    }
    evidence = write_evidence_report(synthetic, root=paths.root)
    return {"stamped": stamped, "evidence_path": str(evidence)}


def rollback_upgrade_job(job_id: str, *, root: Path | None = None) -> dict[str, Any]:
    """Restore install-state.env from the job backup (config rollback, not DB)."""
    paths = _paths(root)
    job = load_upgrade_job(job_id, root=paths.root)
    backup = job.get("backup_path")
    if not backup:
        raise UpgradeError("no backup_path on job")
    src = Path(str(backup)) / "install-state.env"
    if not src.is_file():
        raise UpgradeError(f"backup install-state missing: {src}")
    paths.astloom_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, paths.install_state)
    job["status"] = "rolled_back"
    _mark_step(job, "rollback", "ok", str(src))
    evidence = write_evidence_report(job, root=paths.root)
    job["evidence_path"] = str(evidence)
    return _save_job(job, root=paths.root)


def run_client_upgrade(
    *,
    root: Path | None = None,
    project_dir: Path | None = None,
    server_versions: dict[str, str] | None = None,
    refresh_venv: bool = True,
    rewire_connect: bool = True,
) -> dict[str, Any]:
    """Refresh local CLI (optional) and re-check / re-wire client MCP config."""
    paths = _paths(root)
    work = (project_dir or Path.cwd()).resolve()
    client = client_version_payload()
    server = server_versions or {
        "product_version": PRODUCT_VERSION,
        "contract_version": CONTRACT_VERSION,
        "min_client_contract": CONTRACT_VERSION,
    }
    compat = check_compatibility(
        client_contract=str(client["contract_version"]),
        server_contract=str(server.get("contract_version") or ""),
        min_client_contract=str(server.get("min_client_contract") or ""),
        client_product=str(client["product_version"]),
        server_product=str(server.get("product_version") or ""),
    )
    if not compat.ok:
        raise UpgradeError(compat.reason)

    actions: list[str] = []
    if refresh_venv:
        ensure = paths.root / "scripts" / "ensure-venv.sh"
        if ensure.is_file():
            proc = subprocess.run(
                ["bash", str(ensure)],
                cwd=paths.root,
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                raise UpgradeError(f"ensure-venv failed: {(proc.stderr or proc.stdout)[-1500:]}")
            actions.append("ensure-venv")
        cli = paths.root / ".venv" / "bin" / "astloom"
        if cli.is_file():
            subprocess.run(
                [str(cli), "path", "install"],
                cwd=paths.root,
                capture_output=True,
                text=True,
                check=False,
            )
            actions.append("path-install")

    connect_notes: list[str] = []
    if rewire_connect:
        connect_yaml = work / "connect.yaml"
        if connect_yaml.is_file():
            from astloom_cli.connect_config import load_connect_settings
            from astloom_cli.connect_flow import run_connect

            settings = load_connect_settings(config_path=str(connect_yaml), cwd=work)
            code = run_connect(settings, project_dir=work, dry_run=False)
            connect_notes.append(f"connect exit={code}")
            actions.append("connect")
        else:
            connect_notes.append("no connect.yaml — skipped rewire")

    job = prepare_upgrade_job(
        root=paths.root,
        mode="client",
        risk_level="low",
        enqueue_approval=False,
    )
    job["status"] = "succeeded"
    job["plan"]["compatibility"] = compat.to_dict()
    job["client_actions"] = actions
    job["connect_notes"] = connect_notes
    evidence = write_evidence_report(job, root=paths.root)
    job["evidence_path"] = str(evidence)
    _mark_step(job, "evidence", "ok", str(evidence))
    _save_job(job, root=paths.root)
    return {
        "compatibility": compat.to_dict(),
        "actions": actions,
        "connect_notes": connect_notes,
        "job_id": job["id"],
        "evidence_path": str(evidence),
        "client": client,
        "server": server,
    }
