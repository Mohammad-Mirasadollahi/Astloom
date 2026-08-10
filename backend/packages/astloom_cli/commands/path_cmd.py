"""PATH install command — symlink ~/.local/bin/astloom and persist shell PATH.

Role: make `astloom` available in new shells after install/client bootstrap.
SoT: symlink under ~/.local/bin; PATH export line marked "# Astloom CLI" in shell rc.
Fail closed only when the venv CLI binary is missing; symlink/rc write errors are
reported and non-zero when symlink cannot be created (PATH alone is not enough).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from astloom_cli.util import print_json, repo_root

_RC_MARKER = "# Astloom CLI"


def _shell_name() -> str:
    shell = os.environ.get("SHELL", "") or ""
    base = Path(shell).name.lower()
    if base in {"zsh", "bash", "fish", "sh", "dash", "ksh"}:
        return base
    return "bash"


def default_shell_rc_names(*, shell: str | None = None) -> list[str]:
    """Return relative rc filenames to update for durable PATH (create if missing)."""
    name = (shell or _shell_name()).lower()
    if name == "zsh":
        return [".zshrc"]
    if name == "fish":
        return [".config/fish/config.fish"]
    # bash / sh / unknown — interactive shells load .bashrc
    return [".bashrc"]


def _ensure_bash_profile_sources_bashrc(home: Path) -> dict[str, str] | None:
    """Make sure login shells (SSH) load .bashrc so PATH export applies."""
    profile = home / ".profile"
    marker = "# Astloom CLI bashrc"
    existing = profile.read_text(encoding="utf-8") if profile.is_file() else ""
    if marker in existing or ".bashrc" in existing:
        return {"path": str(profile), "status": "present"}
    block = (
        f"\n{marker}\n"
        'if [ -n "${BASH_VERSION:-}" ]; then\n'
        '  if [ -f "$HOME/.bashrc" ]; then\n'
        '    . "$HOME/.bashrc"\n'
        "  fi\n"
        "fi\n"
    )
    profile.parent.mkdir(parents=True, exist_ok=True)
    with profile.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write(block)
    status = "appended" if existing else "created"
    return {"path": str(profile), "status": status}


def _path_export_line(local_bin: Path, *, fish: bool = False) -> str:
    if fish:
        return f'set -gx PATH "{local_bin}" $PATH  {_RC_MARKER}'
    return f'export PATH="{local_bin}:$PATH"  {_RC_MARKER}'


def _ensure_path_export(rc_file: Path, local_bin: Path) -> str:
    """Append PATH export if missing. Returns status: created|appended|present."""
    fish = rc_file.name == "config.fish"
    line = _path_export_line(local_bin, fish=fish)
    rc_file.parent.mkdir(parents=True, exist_ok=True)
    existing = rc_file.read_text(encoding="utf-8") if rc_file.is_file() else ""
    if _RC_MARKER in existing:
        return "present"
    status = "appended" if rc_file.is_file() and existing else "created"
    with rc_file.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write(f"{line}\n")
    return status


def _resolve_shell_rcs(args: argparse.Namespace) -> list[Path]:
    home = Path(os.path.expanduser("~"))
    if getattr(args, "no_shell_rc", False):
        return []
    explicit = str(getattr(args, "shell_rc", "") or "").strip()
    if explicit:
        return [home / explicit]
    return [home / name for name in default_shell_rc_names()]


def cmd_path_install(args: argparse.Namespace) -> int:
    """Ensure the role-correct CLI name is on PATH (symlink + shell rc PATH export)."""
    quiet = bool(getattr(args, "quiet", False))
    root = repo_root()
    venv_dir = os.environ.get("ASTLOOM_VENV_DIR", ".venv")
    from astloom_cli.service_runtime.paths import install_role

    role = install_role(root)
    # client-only → astloom-client only (no bare astloom on PATH).
    # server / both → bare astloom only (full CLI; no astloom-client on PATH).
    client_only = role == "client"
    bin_name = "astloom-client" if client_only else "astloom"
    source = root / venv_dir / "bin" / bin_name
    if not source.is_file():
        raise SystemExit(
            f"error: {venv_dir}/bin/{bin_name} missing; run: bash scripts/ensure-venv.sh"
        )
    local_bin = Path(os.path.expanduser("~")) / ".local" / "bin"
    target = local_bin / bin_name
    other = local_bin / ("astloom" if client_only else "astloom-client")
    symlink_error: str | None = None
    try:
        local_bin.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or target.exists():
            target.unlink()
        target.symlink_to(source.resolve())
        # Opposite name must not linger on PATH for this install role.
        if other.is_symlink() or other.exists():
            other.unlink()
    except OSError as exc:  # sandbox / read-only home
        symlink_error = str(exc)

    on_path = str(local_bin) in os.environ.get("PATH", "").split(os.pathsep)
    rc_results: list[dict[str, str]] = []
    if symlink_error is None:
        for rc_path in _resolve_shell_rcs(args):
            try:
                status = _ensure_path_export(rc_path, local_bin)
                rc_results.append({"path": str(rc_path), "status": status})
                if not quiet:
                    print(f"PATH export {status} in {rc_path}")
            except OSError as exc:
                rc_results.append({"path": str(rc_path), "status": f"error:{exc}"})
                print(f"warning: could not update shell rc {rc_path}: {exc}")
        # Login shells often only read .profile; ensure it sources .bashrc for bash.
        if not getattr(args, "no_shell_rc", False) and not str(getattr(args, "shell_rc", "") or "").strip():
            if _shell_name() in {"bash", "sh", "dash", "ksh"}:
                try:
                    profile_row = _ensure_bash_profile_sources_bashrc(Path(os.path.expanduser("~")))
                    if profile_row:
                        rc_results.append(profile_row)
                        if not quiet:
                            print(f"login profile {profile_row['status']} in {profile_row['path']}")
                except OSError as exc:
                    print(f"warning: could not update .profile: {exc}")

    if symlink_error is None and (on_path or rc_results):
        hint = None
    elif symlink_error is not None:
        hint = f"venv CLI ready at {source}; PATH symlink skipped ({symlink_error})"
    else:
        hint = f'Add to PATH: export PATH="{local_bin}:$PATH"'

    payload: dict = {
        "symlink": str(target),
        "points_to": str(source.resolve()),
        "cli_name": bin_name,
        "install_role": role or "unknown",
        "removed_other": str(other),
        "local_bin_on_path": on_path,
        "symlink_ok": symlink_error is None,
        "shell_rcs": rc_results,
        "hint": hint,
    }
    if symlink_error is not None:
        payload["symlink_error"] = symlink_error
    if not quiet:
        print_json(payload)
    elif hint:
        print(hint)
    return 0 if symlink_error is None else 1
