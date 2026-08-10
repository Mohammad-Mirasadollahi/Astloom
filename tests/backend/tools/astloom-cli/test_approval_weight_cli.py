"""CLI smoke for approval + weight-profile commands."""

from __future__ import annotations

import json
from pathlib import Path

from astloom_cli.main import main


def test_approval_mode_and_queue(tmp_path, monkeypatch, capsys):
    root = Path("/opt/Astloom")
    monkeypatch.setenv("ASTLOOM_ROOT", str(root))
    import astloom_cli.state as state

    monkeypatch.setattr(state, "default_state_root", lambda _root: tmp_path / "projects")

    assert (
        main(
            [
                "project",
                "register",
                "--tenant",
                "t",
                "--workspace",
                "w",
                "--project",
                "p",
                "--name",
                "Demo",
            ]
        )
        == 0
    )
    assert main(["approval", "mode", "set", "manual", "--tenant", "t", "--workspace", "w", "--project", "p"]) == 0
    capsys.readouterr()
    assert main(["approval", "mode", "show", "--tenant", "t", "--workspace", "w", "--project", "p"]) == 0
    mode = json.loads(capsys.readouterr().out)
    assert mode["mode"] == "manual"

    assert (
        main(
            [
                "approval",
                "enqueue",
                "--tenant",
                "t",
                "--workspace",
                "w",
                "--project",
                "p",
                "--subject-ref",
                "change:9",
                "--subject-class",
                "docs.low_risk",
            ]
        )
        == 0
    )
    item = json.loads(capsys.readouterr().out)
    assert item["status"] == "pending"
    assert main(["approval", "accept", item["id"], "--tenant", "t", "--workspace", "w", "--project", "p"]) == 0
    accepted = json.loads(capsys.readouterr().out)
    assert accepted["status"] == "approved"


def test_weight_profile_cli(tmp_path, monkeypatch, capsys):
    root = Path("/opt/Astloom")
    monkeypatch.setenv("ASTLOOM_ROOT", str(root))
    import astloom_cli.state as state

    monkeypatch.setattr(state, "default_state_root", lambda _root: tmp_path / "projects")

    assert main(["weight-profile", "list"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(row["profile_id"] == "default-memory-profile" for row in payload["profiles"])
    assert main(["weight-profile", "validate", "default-memory-profile"]) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "project",
                "register",
                "--tenant",
                "t",
                "--workspace",
                "w",
                "--project",
                "p",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "weight-profile",
                "activate",
                "conservative-memory-profile",
                "--tenant",
                "t",
                "--workspace",
                "w",
                "--project",
                "p",
                "--reason",
                "test",
            ]
        )
        == 0
    )
    activated = json.loads(capsys.readouterr().out)
    assert activated["active_profile_id"] == "conservative-memory-profile"
    assert (
        main(
            [
                "weight-profile",
                "rollback",
                "--tenant",
                "t",
                "--workspace",
                "w",
                "--project",
                "p",
            ]
        )
        == 0
    )
    rolled = json.loads(capsys.readouterr().out)
    assert rolled["active_profile_id"] == "default-memory-profile"
