"""Unit tests for install runtime selection and PATH helpers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LIB = ROOT / "scripts" / "install"


def _bash_snippet(snippet: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full = f"""
set -euo pipefail
export ASTLOOM_ROOT={ROOT.as_posix()!r}
export ASTLOOM_INSTALL_LIB={LIB.as_posix()!r}
source "{LIB.as_posix()}/common.sh"
{snippet}
"""
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        ["bash", "-c", full],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=merged,
    )


def test_normalize_install_runtime_accepts_venv_host_docker() -> None:
    proc = _bash_snippet(
        "normalize_install_runtime venv; echo; "
        "normalize_install_runtime host; echo; "
        "normalize_install_runtime docker; echo; "
        "normalize_install_runtime weird || echo bad"
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines[:3] == ["venv", "venv", "docker"]
    assert "bad" in lines


def test_normalize_install_role() -> None:
    proc = _bash_snippet(
        "normalize_install_role client; echo; normalize_install_role server; echo; "
        "normalize_install_role both; echo; normalize_install_role dogfood; echo; "
        "normalize_install_role weird || echo bad"
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines[:4] == ["client", "server", "both", "both"]
    assert "bad" in lines


def test_resolve_role_both_keeps_infra(tmp_path: Path) -> None:
    state = tmp_path / "install-state.env"
    proc = _bash_snippet(
        f'INSTALL_STATE_DIR={tmp_path.as_posix()!r}; '
        f'INSTALL_STATE_FILE={state.as_posix()!r}; '
        "INSTALL_ROLE=both; resolve_install_role; "
        'printf "%s\\n" "${INSTALL_ROLE}" "${INSTALL_SKIP_INFRA}"',
        env={"INSTALL_NONINTERACTIVE": "1", "INSTALL_ASSUME_YES": "1", "INSTALL_SKIP_INFRA": "0"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines[-2:] == ["both", "0"]
    assert "role=both" in state.read_text(encoding="utf-8")


def test_resolve_runtime_honors_flag_noninteractive() -> None:
    proc = _bash_snippet(
        "INSTALL_ROLE=server; resolve_install_runtime; printf '%s\\n' \"${INSTALL_RUNTIME}\"",
        env={"INSTALL_NONINTERACTIVE": "1", "INSTALL_RUNTIME": "docker", "INSTALL_SKIP_INFRA": "0"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == "docker"


def test_resolve_runtime_defaults_venv_when_noninteractive(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_file = state_dir / "install-state.env"
    proc = _bash_snippet(
        f'''
INSTALL_STATE_DIR="{state_dir.as_posix()}"
INSTALL_STATE_FILE="{state_file.as_posix()}"
INSTALL_RUNTIME=""
INSTALL_ROLE=server
resolve_install_runtime
printf "%s\\n" "${{INSTALL_RUNTIME}}"
''',
        env={"INSTALL_NONINTERACTIVE": "1"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == "venv"


def test_resolve_role_ignores_polluted_banner_value(tmp_path: Path) -> None:
    """Older prompt-capture bugs wrote banner text into role=; must heal."""
    state = tmp_path / "install-state.env"
    state.write_text("role=server\n", encoding="utf-8")
    proc = _bash_snippet(
        f'INSTALL_STATE_DIR={tmp_path.as_posix()!r}; '
        f'INSTALL_STATE_FILE={state.as_posix()!r}; '
        'INSTALL_ROLE="[astloom-install] ================================================================"; '
        'resolve_install_role; printf "%s\\n" "${INSTALL_ROLE}"',
        env={"INSTALL_NONINTERACTIVE": "1", "INSTALL_ASSUME_YES": "1"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == "server"
    assert "Ignoring invalid INSTALL_ROLE" in (proc.stderr + proc.stdout)


def test_install_stdout_token_keeps_last_line() -> None:
    proc = _bash_snippet(
        'install_stdout_token $\'banner\\nclient\\n\'; echo; '
        'install_stdout_token "server"'
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines[:2] == ["client", "server"]


def test_resolve_role_client_from_skip_infra() -> None:
    proc = _bash_snippet(
        "INSTALL_ROLE=; resolve_install_role; printf '%s\\n' \"${INSTALL_ROLE}\" \"${INSTALL_SKIP_INFRA}\"",
        env={"INSTALL_NONINTERACTIVE": "1", "INSTALL_SKIP_INFRA": "1"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines[-2:] == ["client", "1"]


def test_client_role_skips_runtime_prompt() -> None:
    proc = _bash_snippet(
        "INSTALL_ROLE=client; INSTALL_RUNTIME=; resolve_install_runtime; "
        "printf '%s\\n' \"${INSTALL_RUNTIME}\"",
        env={"INSTALL_NONINTERACTIVE": "1"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == "venv"


def test_docker_runtime_rejects_skip_infra() -> None:
    proc = _bash_snippet(
        "INSTALL_ROLE=server; resolve_install_runtime",
        env={"INSTALL_NONINTERACTIVE": "1", "INSTALL_RUNTIME": "docker", "INSTALL_SKIP_INFRA": "1"},
    )
    assert proc.returncode != 0
    assert "skip-infra" in (proc.stderr + proc.stdout).lower()


def test_normalize_install_action() -> None:
    proc = _bash_snippet(
        "normalize_install_action install; echo; normalize_install_action upgrade; echo; "
        "normalize_install_action weird || echo bad"
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines[:2] == ["install", "upgrade"]
    assert "bad" in lines


def test_normalize_yes_no_accepts_y_n() -> None:
    proc = _bash_snippet(
        "normalize_yes_no y; echo; normalize_yes_no YES; echo; "
        "normalize_yes_no n; echo; normalize_yes_no No; echo; "
        "normalize_yes_no maybe || echo bad; echo; "
        "normalize_yes_no '' || echo empty"
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines[:4] == ["yes", "yes", "no", "no"]
    assert "bad" in lines and "empty" in lines


def test_confirm_install_action_requires_exact_yes() -> None:
    proc = _bash_snippet(
        "confirm_install_action install <<'EOF'\nno\nEOF",
        env={"INSTALL_NONINTERACTIVE": "0", "INSTALL_ASSUME_YES": "0"},
    )
    # Without stdin TTY and without usable /dev/tty, confirm fails closed
    # unless --yes/--non-interactive (curl|bash uses /dev/tty when present).
    assert proc.returncode != 0


def test_install_can_prompt_respects_noninteractive() -> None:
    proc = _bash_snippet(
        "install_can_prompt && echo yes || echo no",
        env={"INSTALL_NONINTERACTIVE": "1"},
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == "no"


def test_confirm_install_action_skips_with_assume_yes() -> None:
    proc = _bash_snippet(
        "confirm_install_action upgrade; echo ok",
        env={"INSTALL_ASSUME_YES": "1"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "ok" in proc.stdout


def test_resolve_action_noninteractive_defaults_install() -> None:
    proc = _bash_snippet(
        "resolve_install_action; printf '%s\\n' \"${INSTALL_ACTION}\"",
        env={"INSTALL_NONINTERACTIVE": "1", "INSTALL_ASSUME_YES": "0"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == "install"


def test_resolve_action_locked_upgrade() -> None:
    proc = _bash_snippet(
        "INSTALL_ACTION_LOCKED=1; resolve_install_action upgrade; "
        "printf '%s\\n' \"${INSTALL_ACTION}\"",
        env={"INSTALL_NONINTERACTIVE": "1"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == "upgrade"


def test_install_help_mentions_role_and_venv() -> None:
    proc = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--role" in proc.stdout
    assert "--runtime" in proc.stdout
    assert "--yes" in proc.stdout
    assert "venv" in proc.stdout and "docker" in proc.stdout
    assert "client" in proc.stdout.lower() and "server" in proc.stdout.lower()
    assert "upgrade" in proc.stdout.lower()
    assert "yes" in proc.stdout.lower()


def test_prompt_menus_go_to_stderr_and_confirm_still_asks_yes() -> None:
    """Menus must not pollute $(prompt_*) capture; interactive confirm still asks for yes."""
    text = (LIB / "common.sh").read_text(encoding="utf-8")
    assert "cat >&2 <<'EOF'" in text
    assert '$*" >&2; }' in text or '"$*" >&2; }' in text
    assert "Continue with ${action}? [y/n]" in text or "[y/n]" in text
    assert "normalize_yes_no" in text
    assert "Choose 1 or 2 (no default)" in text
    assert "Confirmation skipped" in text
    # Interactive choice prompts must not offer Enter-as-default.
    assert "default: 1" not in text
    assert "default: 2" not in text


def test_resolve_data_root_flag_and_default(tmp_path: Path) -> None:
    state = tmp_path / "install-state.env"
    custom = tmp_path / "my-data"
    proc = _bash_snippet(
        f'INSTALL_STATE_DIR={tmp_path.as_posix()!r}; '
        f'INSTALL_STATE_FILE={state.as_posix()!r}; '
        "INSTALL_ROLE=server; INSTALL_SKIP_INFRA=0; "
        f'ASTLOOM_DATA_ROOT={custom.as_posix()!r}; '
        "resolve_install_data_root; printf '%s\\n' \"${ASTLOOM_DATA_ROOT}\"",
        env={"INSTALL_NONINTERACTIVE": "1", "INSTALL_ASSUME_YES": "1"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == str(custom.resolve())
    assert f"data_root={custom.resolve()}" in state.read_text(encoding="utf-8")
    assert (custom / "postgres").is_dir()


def test_resolve_data_root_noninteractive_default(tmp_path: Path) -> None:
    state = tmp_path / "install-state.env"
    proc = _bash_snippet(
        f'INSTALL_STATE_DIR={tmp_path.as_posix()!r}; '
        f'INSTALL_STATE_FILE={state.as_posix()!r}; '
        "INSTALL_ROLE=server; INSTALL_SKIP_INFRA=0; "
        "unset ASTLOOM_DATA_ROOT || true; "
        "resolve_install_data_root; printf '%s\\n' \"${ASTLOOM_DATA_ROOT}\"",
        env={"INSTALL_NONINTERACTIVE": "1", "INSTALL_ASSUME_YES": "1"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    # Snippet exports ASTLOOM_ROOT=repo; default is sibling *-data of that root.
    expected = f"{ROOT.parent / (ROOT.name + '-data')}"
    # normalize may resolve; compare resolved forms
    got = proc.stdout.strip().splitlines()[-1]
    assert Path(got).resolve() == Path(expected).resolve()


def test_resolve_data_root_skipped_for_client(tmp_path: Path) -> None:
    state = tmp_path / "install-state.env"
    proc = _bash_snippet(
        f'INSTALL_STATE_DIR={tmp_path.as_posix()!r}; '
        f'INSTALL_STATE_FILE={state.as_posix()!r}; '
        "INSTALL_ROLE=client; INSTALL_SKIP_INFRA=1; "
        "unset ASTLOOM_DATA_ROOT || true; "
        "resolve_install_data_root; "
        'if [[ -n "${ASTLOOM_DATA_ROOT:-}" ]]; then echo SET; else echo UNSET; fi',
        env={"INSTALL_NONINTERACTIVE": "1", "INSTALL_ASSUME_YES": "1"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == "UNSET"
    text = state.read_text(encoding="utf-8") if state.is_file() else ""
    assert "data_root=" not in text


def test_prompt_copy_mentions_client_or_server() -> None:
    text = (LIB / "common.sh").read_text(encoding="utf-8")
    assert "Install client, server, or both" in text
    assert "Install new or upgrade existing" in text
    assert "1=venv" in text or "venv" in text
    assert "prompt_install_role" in text
    assert "prompt_install_action" in text
    assert "confirm_install_action" in text
    assert "install_can_prompt" in text
    assert "install_read_line" in text
    assert "/dev/tty" in text


def test_prompt_copy_mentions_data_root() -> None:
    text = (LIB / "common.sh").read_text(encoding="utf-8")
    assert "prompt_install_data_root" in text
    assert "resolve_install_data_root" in text
    assert "Data root [Enter = default]" in text
    install = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "--data-root" in install


def test_list_stages_includes_runtime_bringup() -> None:
    proc = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "--list-stages"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "06_runtime_bringup" in proc.stdout
