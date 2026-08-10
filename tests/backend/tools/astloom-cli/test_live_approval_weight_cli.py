"""Live probe: real astloom approval + weight-profile CLI end-to-end."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
ASTLOOM = ROOT / ".venv" / "bin" / "astloom"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ASTLOOM_ROOT"] = os.environ.get("ASTLOOM_LIVE_TEST_ROOT", str(ROOT))
    return subprocess.run(
        [str(ASTLOOM), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _must_json(label: str, args: list[str]) -> dict:
    proc = _run(args)
    assert proc.returncode == 0, f"{label}: exit={proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    return json.loads(proc.stdout)


@pytest.mark.live
def test_live_approval_and_weight_profile_cli(tmp_path: Path, monkeypatch) -> None:
    if not ASTLOOM.is_file():
        pytest.skip("astloom CLI not installed in .venv")

    monkeypatch.setenv("ASTLOOM_LIVE_TEST_ROOT", str(tmp_path))
    tenant = "live-qa"
    workspace = "approval"
    project = f"p-{int(time.time())}"
    scope = ["--tenant", tenant, "--workspace", workspace, "--project", project]
    gov_path = tmp_path / ".astloom" / "weight-profile-governance.json"
    # Known baseline so rollback assertions are stable on a shared host.
    if gov_path.is_file():
        gov_path.unlink()

    try:
        _must_json(
            "register",
            ["project", "register", *scope, "--name", "Live approval QA", "--force"],
        )
        mode = _must_json("mode show", ["approval", "mode", "show", *scope])
        assert mode["mode"] in {"manual", "auto_approve", "system_routed"}

        _must_json("mode manual", ["approval", "mode", "set", "manual", *scope])
        pending = _must_json(
            "enqueue",
            [
                "approval",
                "enqueue",
                *scope,
                "--subject-ref",
                "change:live-1",
                "--subject-class",
                "docs.low_risk",
                "--reason",
                "live qa ask",
            ],
        )
        assert pending["status"] == "pending"
        aid = pending["id"]

        _must_json("mode auto", ["approval", "mode", "set", "auto_approve", *scope])
        blocked = _must_json(
            "hard-block",
            [
                "approval",
                "enqueue",
                *scope,
                "--subject-ref",
                "change:secret",
                "--subject-class",
                "secret.exposure",
            ],
        )
        assert blocked["status"] == "pending"
        assert blocked["route_decision"]["hard_block"] is True

        auto = _must_json(
            "auto-approve",
            [
                "approval",
                "enqueue",
                *scope,
                "--subject-ref",
                "change:auto",
                "--subject-class",
                "docs.low_risk",
            ],
        )
        assert auto["status"] == "approved"

        by_id = _must_json("queue id", ["approval", "queue", *scope, "--id", aid])
        assert by_id["count"] == 1
        since_q = _must_json("queue since", ["approval", "queue", *scope, "--since", "1h", "--all"])
        assert since_q["count"] >= 1
        shown = _must_json("show", ["approval", "show", aid, *scope])
        assert shown["reason"] == "live qa ask"

        accepted = _must_json("accept", ["approval", "accept", aid, *scope, "--reason", "live ok"])
        assert accepted["status"] == "approved"
        rejected = _must_json(
            "reject",
            ["approval", "reject", blocked["id"], *scope, "--reason", "denied"],
        )
        assert rejected["status"] == "rejected"

        profiles = _must_json("weight list", ["weight-profile", "list"])
        assert any(p["profile_id"] == "default-memory-profile" for p in profiles["profiles"])
        activated = _must_json(
            "weight activate",
            ["weight-profile", "activate", "conservative-memory-profile", *scope, "--reason", "live"],
        )
        assert activated["active_profile_id"] == "conservative-memory-profile"
        again = _must_json(
            "weight activate idempotent",
            ["weight-profile", "activate", "conservative-memory-profile", *scope, "--reason", "again"],
        )
        assert again.get("unchanged") is True
        rolled = _must_json("weight rollback", ["weight-profile", "rollback", *scope])
        assert rolled["active_profile_id"] == "default-memory-profile"
    finally:
        for name in (f"{project}.json", f"{project}.approvals.json"):
            path = tmp_path / ".astloom" / "projects" / tenant / workspace / name
            if path.is_file():
                path.unlink()
        if gov_path.is_file():
            gov_path.unlink()
