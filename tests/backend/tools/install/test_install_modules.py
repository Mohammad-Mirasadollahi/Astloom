"""Unit checks for Astloom modular install (no full OS/docker mutation)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
INSTALL_SH = ROOT / "install.sh"
INSTALL_LIB = ROOT / "scripts" / "install"

REQUIRED_MODULES = (
    "common.sh",
    "load.sh",
    "01_prerequisites.sh",
    "02_venv.sh",
    "03_compose_env.sh",
    "04_docker_infra.sh",
    "05_verify.sh",
    "README.md",
)


def test_install_entrypoint_exists_and_executable() -> None:
    assert INSTALL_SH.is_file()
    assert os.access(INSTALL_SH, os.X_OK)


@pytest.mark.parametrize("name", REQUIRED_MODULES)
def test_install_module_present(name: str) -> None:
    path = INSTALL_LIB / name
    assert path.is_file(), f"missing install module: {path}"


def test_install_help_exits_zero() -> None:
    proc = subprocess.run(
        ["bash", str(INSTALL_SH), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "Astloom installer" in proc.stdout
    assert "--check" in proc.stdout
    assert "--upgrade" in proc.stdout
    assert "--mint-api-key" in proc.stdout
    assert "--no-mint-api-key" in proc.stdout


def test_install_list_stages_order() -> None:
    proc = subprocess.run(
        ["bash", str(INSTALL_SH), "--list-stages"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    body = proc.stdout
    expected = [
        "01_prerequisites",
        "02_venv",
        "03_compose_env",
        "04_docker_infra",
        "05_verify",
    ]
    positions = [body.index(name) for name in expected]
    assert positions == sorted(positions)


def test_resolve_install_api_key_upgrade_skips_mint() -> None:
    script = r"""
set -euo pipefail
export ASTLOOM_ROOT="%s"
export INSTALL_ACTION=upgrade
export INSTALL_ROLE=server
export INSTALL_NONINTERACTIVE=1
export INSTALL_MINT_API_KEY=
# shellcheck source=/dev/null
source "%s/common.sh"
resolve_install_api_key
test "${INSTALL_MINT_API_KEY}" = "0"
echo OK
""" % (
        ROOT,
        INSTALL_LIB,
    )
    proc = subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_resolve_install_api_key_flag_forces_mint() -> None:
    script = r"""
set -euo pipefail
export ASTLOOM_ROOT="%s"
export INSTALL_ACTION=install
export INSTALL_ROLE=server
export INSTALL_NONINTERACTIVE=1
export INSTALL_MINT_API_KEY=1
export INSTALL_API_KEY_TENANT=mir
export INSTALL_API_KEY_WORKSPACE=dev
export INSTALL_API_KEY_PROJECT=App
export INSTALL_API_KEY_TTL_SECONDS=0
# shellcheck source=/dev/null
source "%s/common.sh"
resolve_install_api_key
test "${INSTALL_MINT_API_KEY}" = "1"
test "${INSTALL_API_KEY_TENANT}" = "mir"
echo OK
""" % (
        ROOT,
        INSTALL_LIB,
    )
    proc = subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_prerequisites_check_fails_without_ensurepip() -> None:
    """Stage 01 must not treat Python-without-ensurepip as satisfied."""
    script = f"""
set -euo pipefail
export ASTLOOM_ROOT={ROOT.as_posix()!r}
export INSTALL_SKIP_INFRA=1
export INSTALL_WITH_FRONTEND=0
source {INSTALL_LIB.as_posix()!r}/common.sh
source {INSTALL_LIB.as_posix()!r}/01_prerequisites.sh
python_ensurepip_ok() {{ return 1; }}
if stage_01_prerequisites_check; then
  echo "expected check failure" >&2
  exit 2
fi
echo OK
"""
    proc = subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "OK" in proc.stdout
    assert "ensurepip" in (proc.stderr + proc.stdout).lower()


def test_ensure_python312_installs_venv_when_ensurepip_missing() -> None:
    """Existing python3.12 must still apt-install python3.12-venv when ensurepip is gone."""
    with tempfile.TemporaryDirectory() as tmp:
        script = f"""
set -euo pipefail
export ASTLOOM_ROOT={tmp!r}
source {INSTALL_LIB.as_posix()!r}/common.sh
source {INSTALL_LIB.as_posix()!r}/01_prerequisites.sh
python_bin() {{ printf '%s\\n' python3.12; }}
python_ensurepip_ok() {{
  # Fail until apt installs python3.12-venv (second call succeeds).
  if [[ -f "${{ASTLOOM_ROOT}}/venv_pkg_installed" ]]; then
    return 0
  fi
  return 1
}}
as_root() {{
  printf '%s\\n' "$*" >>"${{ASTLOOM_ROOT}}/as_root.log"
  if [[ "$*" == *python3.12-venv* ]]; then
    touch "${{ASTLOOM_ROOT}}/venv_pkg_installed"
  fi
}}
_stage_01_ensure_python312
grep -q 'python3.12-venv' "${{ASTLOOM_ROOT}}/as_root.log"
echo OK
"""
        proc = subprocess.run(
            ["bash", "-c", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "OK" in proc.stdout


def test_ensure_venv_script_mentions_ensurepip_on_failure() -> None:
    text = (ROOT / "scripts" / "ensure-venv.sh").read_text(encoding="utf-8")
    assert "|| true" not in text.split("pip install", 1)[0]
    assert "python3.12-venv" in text
    assert "ensurepip" in text


def test_seed_repo_operator_files_copies_examples(tmp_path: Path) -> None:
    """Install seeds .env and astloom.sync.yaml from examples when missing."""
    (tmp_path / ".env.example").write_text("ASTLOOM_TENANT_ID=demo\n", encoding="utf-8")
    (tmp_path / "astloom.sync.yaml.example").write_text(
        "code:\n  exclude: []\ndocs:\n  match: []\n",
        encoding="utf-8",
    )
    script = r"""
set -euo pipefail
export ASTLOOM_ROOT="%s"
source "%s/common.sh"
seed_repo_operator_files
test -f "${ASTLOOM_ROOT}/.env"
test -f "${ASTLOOM_ROOT}/astloom.sync.yaml"
grep -q 'ASTLOOM_TENANT_ID=demo' "${ASTLOOM_ROOT}/.env"
# Second call must not overwrite
echo KEEP > "${ASTLOOM_ROOT}/.env"
seed_repo_operator_files
grep -q KEEP "${ASTLOOM_ROOT}/.env"
echo OK
""" % (
        tmp_path,
        INSTALL_LIB,
    )
    proc = subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "OK" in proc.stdout


def test_prerequisites_skip_docker_install_when_skip_infra() -> None:
    """Client/--skip-infra must not apt-install docker.io even if Docker is missing."""
    with tempfile.TemporaryDirectory() as tmp:
        script = f"""
set -euo pipefail
export ASTLOOM_ROOT={tmp!r}
export ASTLOOM_INSTALL_LIB={INSTALL_LIB.as_posix()!r}
export INSTALL_SKIP_INFRA=1
export INSTALL_SKIP_PREREQS=0
export INSTALL_CHECK_ONLY=0
export INSTALL_WITH_FRONTEND=0
source {INSTALL_LIB.as_posix()!r}/common.sh
source {INSTALL_LIB.as_posix()!r}/01_prerequisites.sh

linux_debian_family() {{ return 0; }}
_stage_01_ensure_python312() {{ :; }}
have_cmd() {{ return 1; }}
as_root() {{
  printf 'ROOT_CMD %s\\n' "$*" >>"${{ASTLOOM_ROOT}}/as_root.log"
}}
mkdir -p "${{ASTLOOM_ROOT}}"
: >"${{ASTLOOM_ROOT}}/as_root.log"

_check_n=0
stage_01_prerequisites_check() {{
  _check_n=$((_check_n + 1))
  if [[ "${{_check_n}}" -eq 1 ]]; then
    return 1
  fi
  return 0
}}

stage_01_prerequisites_run
if grep -E 'docker\\.io|docker-compose|systemctl.*docker|usermod.*docker' \
  "${{ASTLOOM_ROOT}}/as_root.log"; then
  exit 2
fi
grep -q 'apt-get update' "${{ASTLOOM_ROOT}}/as_root.log"
grep -q 'ca-certificates' "${{ASTLOOM_ROOT}}/as_root.log"
echo OK
"""
        proc = subprocess.run(
            ["bash", "-c", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "OK" in proc.stdout
    assert "Skipping Docker Engine install" in (proc.stderr + proc.stdout)


def test_role_client_sets_skip_infra_in_entrypoint() -> None:
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "export INSTALL_SKIP_INFRA=1" in text
    assert "client | CLIENT" in text


def test_stage_banners_use_six_total() -> None:
    for name in (
        "01_prerequisites.sh",
        "02_venv.sh",
        "03_compose_env.sh",
        "04_docker_infra.sh",
        "05_verify.sh",
        "06_runtime_bringup.sh",
    ):
        text = (INSTALL_LIB / name).read_text(encoding="utf-8")
        assert "Stage " in text
        assert "/06" in text
        assert "/05 —" not in text and "/05 -" not in text


def test_install_cli_uses_path_quiet() -> None:
    text = (INSTALL_LIB / "common.sh").read_text(encoding="utf-8")
    assert "path install --quiet" in text
    assert "path_shim_matches_venv" in text


def test_unknown_flag_exits_nonzero() -> None:
    proc = subprocess.run(
        ["bash", str(INSTALL_SH), "--not-a-real-flag"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0


def test_install_cli_on_path_writes_shim_and_shell_rc(tmp_path: Path) -> None:
    """Stage-02 helper must create ~/.local/bin/astloom even if PATH already has it."""
    home = tmp_path / "home"
    local_bin = home / ".local" / "bin"
    local_bin.mkdir(parents=True)
    bashrc = home / ".bashrc"
    bashrc.write_text("# pretest\n", encoding="utf-8")
    # Fake venv astloom that delegates to the real CLI for `path install`.
    fake_venv = tmp_path / "venv" / "bin"
    fake_venv.mkdir(parents=True)
    real_cli = ROOT / ".venv" / "bin" / "astloom"
    if not real_cli.is_file():
        pytest.skip("project .venv/bin/astloom required")
    fake_cli = fake_venv / "astloom"
    fake_cli.symlink_to(real_cli)

    script = r"""
set -euo pipefail
export ASTLOOM_ROOT="%s"
export INSTALL_ROLE=server
export HOME="%s"
export SHELL=/bin/bash
export PATH="%s:${PATH}"
source "%s/common.sh"
install_cli_on_path "%s"
user_cli_on_path
grep -q 'Astloom CLI' "${HOME}/.bashrc"
test -e "${HOME}/.local/bin/astloom"
command -v astloom >/dev/null
echo OK
""" % (
        ROOT,
        home,
        local_bin,
        INSTALL_LIB,
        fake_cli,
    )
    proc = subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HOME": str(home), "ASTLOOM_ROOT": str(ROOT), "SHELL": "/bin/bash"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "OK" in proc.stdout
    assert (home / ".local" / "bin" / "astloom").exists()
    assert "Astloom CLI" in bashrc.read_text(encoding="utf-8")


def test_install_cli_on_path_creates_bashrc_when_missing(tmp_path: Path) -> None:
    """Client machines often lack ~/.bashrc; PATH must still persist by default."""
    home = tmp_path / "home"
    home.mkdir()
    fake_venv = tmp_path / "venv" / "bin"
    fake_venv.mkdir(parents=True)
    real_cli = ROOT / ".venv" / "bin" / "astloom"
    if not real_cli.is_file():
        pytest.skip("project .venv/bin/astloom required")
    fake_cli = fake_venv / "astloom"
    fake_cli.symlink_to(real_cli)

    script = r"""
set -euo pipefail
export ASTLOOM_ROOT="%s"
export INSTALL_ROLE=server
export HOME="%s"
export SHELL=/bin/bash
source "%s/common.sh"
install_cli_on_path "%s"
test -f "${HOME}/.bashrc"
grep -q 'Astloom CLI' "${HOME}/.bashrc"
test -e "${HOME}/.local/bin/astloom"
echo OK
""" % (ROOT, home, INSTALL_LIB, fake_cli)
    proc = subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HOME": str(home), "ASTLOOM_ROOT": str(ROOT), "SHELL": "/bin/bash"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "OK" in proc.stdout
    assert "Astloom CLI" in (home / ".bashrc").read_text(encoding="utf-8")


def test_stage_02_requires_path_shim_in_check() -> None:
    body = (INSTALL_LIB / "02_venv.sh").read_text(encoding="utf-8")
    assert "user_cli_on_path" in body
    assert "install_cli_on_path" in body
    assert "|| true" not in body
    common = (INSTALL_LIB / "common.sh").read_text(encoding="utf-8")
    assert "install_cli_on_path()" in common
    assert "user_cli_on_path()" in common
