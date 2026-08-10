"""Smoke tests for the modular Astloom installer.

Host smoke always runs (venv + CLI + compose env). Docker/infra smoke is
marked live and skips when the daemon is unavailable unless
ASTLOOM_SMOKE_REQUIRE_DOCKER=1.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SMOKE_SH = ROOT / "tests" / "e2e" / "install" / "run-install-smoke.sh"


def _docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    info = subprocess.run(
        ["docker", "info"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if info.returncode != 0:
        return False
    compose = subprocess.run(
        ["docker", "compose", "version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return compose.returncode == 0


def _run_smoke(env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(SMOKE_SH)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=int(os.environ.get("ASTLOOM_INSTALL_SMOKE_TIMEOUT", "600")),
    )


def test_install_smoke_script_exists_and_executable() -> None:
    assert SMOKE_SH.is_file()
    assert os.access(SMOKE_SH, os.X_OK)


def test_install_smoke_host_path() -> None:
    """Always-on smoke: prerequisites/venv/CLI/compose-env without Docker."""
    proc = _run_smoke({"SMOKE_SKIP_DOCKER": "1"})
    assert proc.returncode == 0, (
        f"host install smoke failed (exit {proc.returncode})\n"
        f"--- stdout ---\n{proc.stdout[-4000:]}\n"
        f"--- stderr ---\n{proc.stderr[-4000:]}"
    )
    assert "SMOKE PASSED" in proc.stdout
    assert "astloom doctor" in proc.stdout or "OK  astloom doctor" in proc.stdout


@pytest.mark.live
def test_install_smoke_with_docker() -> None:
    """Full install including Compose Postgres/Neo4j when Docker works."""
    require = os.environ.get("ASTLOOM_SMOKE_REQUIRE_DOCKER", "0") == "1"
    if not _docker_ready():
        if require:
            pytest.fail("Docker required for live install smoke but daemon is unavailable")
        pytest.skip("Docker daemon not reachable; host smoke still covers non-infra path")

    proc = _run_smoke({"SMOKE_SKIP_DOCKER": "0", "SMOKE_REQUIRE_DOCKER": "1"})
    assert proc.returncode == 0, (
        f"docker install smoke failed (exit {proc.returncode})\n"
        f"--- stdout ---\n{proc.stdout[-6000:]}\n"
        f"--- stderr ---\n{proc.stderr[-4000:]}"
    )
    assert "SMOKE PASSED" in proc.stdout
    assert "docker infra smoke passed" in proc.stdout or "OK  full install.sh" in proc.stdout
