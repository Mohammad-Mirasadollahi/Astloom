"""Unit tests for Astloom upgrade compatibility and control-plane jobs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astloom_cli.upgrade.compat import check_compatibility
from astloom_cli.upgrade.engine import (
    UpgradeError,
    create_upgrade_plan,
    prepare_upgrade_job,
    rollback_upgrade_job,
    run_upgrade_job,
)
from astloom_cli.upgrade.versions import (
    CONTRACT_VERSION,
    PRODUCT_VERSION,
    stamp_install_versions,
)


def test_compatibility_same_contract_ok() -> None:
    result = check_compatibility(
        client_contract=CONTRACT_VERSION,
        server_contract=CONTRACT_VERSION,
        min_client_contract=CONTRACT_VERSION,
        client_product=PRODUCT_VERSION,
        server_product=PRODUCT_VERSION,
    )
    assert result.ok
    assert result.status == "compatible"


def test_compatibility_product_drift_advisory() -> None:
    result = check_compatibility(
        client_contract="1",
        server_contract="1",
        client_product="0.1.0",
        server_product="0.2.0",
    )
    assert result.ok
    assert result.status == "advisory"


def test_compatibility_contract_mismatch_fails() -> None:
    result = check_compatibility(
        client_contract="1",
        server_contract="2",
        min_client_contract="2",
        client_product="0.1.0",
        server_product="0.2.0",
    )
    assert not result.ok
    assert result.status == "incompatible"


def test_stamp_and_plan(tmp_path: Path) -> None:
    stamp_install_versions(tmp_path, runtime="host")
    plan = create_upgrade_plan(root=tmp_path, mode="local", risk_level="low")
    assert plan["runtime"] == "host"
    assert plan["target"]["contract_version"] == CONTRACT_VERSION
    assert plan["compatibility"]["ok"] is True
    assert plan["requires_approval"] is False


def test_control_plane_requires_approval(tmp_path: Path) -> None:
    stamp_install_versions(tmp_path, runtime="docker")
    plan = create_upgrade_plan(root=tmp_path, mode="control-plane", risk_level="high")
    assert plan["requires_approval"] is True


def test_prepare_run_skip_deploy_and_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stamp_install_versions(tmp_path, runtime="host")
    state = tmp_path / ".astloom" / "install-state.env"
    original = state.read_text(encoding="utf-8")

    # Avoid real doctor/install; only exercise job + backup + stamp path.
    monkeypatch.setattr(
        "astloom_cli.upgrade.engine._run_doctor",
        lambda root: None,
    )

    job = prepare_upgrade_job(
        root=tmp_path,
        mode="local",
        risk_level="low",
        enqueue_approval=False,
    )
    assert job["status"] == "approved"
    job_id = job["id"]

    result = run_upgrade_job(job_id, root=tmp_path, yes=True, skip_deploy=True)
    assert result["status"] == "succeeded"
    assert Path(result["backup_path"]).is_dir()
    assert Path(result["evidence_path"]).is_file()

    # Mutate state then rollback.
    state.write_text(original + "mutated=1\n", encoding="utf-8")
    rolled = rollback_upgrade_job(job_id, root=tmp_path)
    assert rolled["status"] == "rolled_back"
    assert "mutated=" not in state.read_text(encoding="utf-8")


def test_prepare_without_install_state_fails(tmp_path: Path) -> None:
    with pytest.raises(UpgradeError, match="install-state"):
        prepare_upgrade_job(root=tmp_path, mode="local", enqueue_approval=False)


def test_upgrade_cli_help() -> None:
    from astloom_cli.parser import build_parser

    parser = build_parser()
    args = parser.parse_args(["upgrade", "versions"])
    assert args.command == "upgrade"
    assert args.upgrade_command == "versions"


def test_ping_payload_keys() -> None:
    from astloom_cli.upgrade.versions import server_version_payload

    payload = server_version_payload()
    assert set(payload) >= {"product_version", "contract_version", "min_client_contract"}


def test_check_from_ping_roundtrip(tmp_path: Path) -> None:
    from astloom_cli.commands.upgrade import cmd_upgrade_check
    import argparse

    ping = {
        "product_version": PRODUCT_VERSION,
        "contract_version": CONTRACT_VERSION,
        "min_client_contract": CONTRACT_VERSION,
    }
    path = tmp_path / "ping.json"
    path.write_text(json.dumps(ping), encoding="utf-8")
    ns = argparse.Namespace(
        from_ping=str(path),
        assume_local_server=False,
        server_product="",
        server_contract="",
        min_client_contract="",
    )
    assert cmd_upgrade_check(ns) == 0
