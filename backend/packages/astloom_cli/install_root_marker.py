"""Well-known Astloom install-root markers (no-root-required discovery).

Role: stamp the absolute Astloom checkout path after install/first run for
operator inspection. Source of truth: plain-text ``install-root`` files (one
absolute path per line). Allowed: user-home + in-tree markers (mode 0644);
SUDO_USER home when install ran via sudo. Forbidden: world-writable temp
paths; treating unvalidated paths as Astloom roots; requiring root to read
markers.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

MARKER_NAME = "install-root"
_ABS_PATH_RE = re.compile(r"^(/|[A-Za-z]:[\\/]).+")


def looks_like_astloom_root(root: Path) -> bool:
    """True when *root* looks like an Astloom checkout (readable without root)."""
    try:
        path = root.expanduser().resolve()
    except OSError:
        return False
    if not path.is_dir():
        return False
    if (path / ".venv" / "bin" / "astloom").is_file():
        return True
    if (path / ".venv" / "Scripts" / "astloom.exe").is_file():
        return True
    pyproject = path / "pyproject.toml"
    if pyproject.is_file():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        if 'name = "astloom"' in text or "name='astloom'" in text:
            return True
    return (path / "backend" / "packages" / "astloom_cli").is_dir()


def marker_path_in_tree(root: Path) -> Path:
    return root.expanduser().resolve() / ".astloom" / MARKER_NAME


def marker_path_in_home(home: Path | None = None) -> Path:
    base = (home or Path.home()).expanduser()
    return base / ".astloom" / MARKER_NAME


def marker_path_xdg_state() -> Path | None:
    raw = (os.environ.get("XDG_STATE_HOME") or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser() / "astloom" / MARKER_NAME


def read_marker_file(path: Path) -> Path | None:
    """Return absolute install root from a marker file, or None if missing/invalid."""
    try:
        if not path.is_file():
            return None
        line = path.read_text(encoding="utf-8").splitlines()[0].strip()
    except OSError:
        return None
    if not line or not _ABS_PATH_RE.match(line):
        return None
    candidate = Path(line).expanduser()
    if looks_like_astloom_root(candidate):
        return candidate.resolve()
    return None


def stamp_install_root(
    root: Path,
    *,
    home: Path | None = None,
    extra_homes: list[Path] | None = None,
) -> list[Path]:
    """Write install-root markers; return paths successfully written.

    Always stamps ``<root>/.astloom/install-root`` (mode 0644 when possible) so
    non-root users can read an install under ``/opt/...``. Also stamps the
    current user home (and optional extra homes such as ``SUDO_USER``).
    """
    resolved = root.expanduser().resolve()
    if not looks_like_astloom_root(resolved):
        raise ValueError(f"not an Astloom root: {resolved}")
    payload = f"{resolved}\n"
    targets: list[Path] = [marker_path_in_tree(resolved), marker_path_in_home(home)]
    xdg = marker_path_xdg_state()
    if xdg is not None:
        targets.append(xdg)
    for extra in extra_homes or []:
        targets.append(marker_path_in_home(extra))

    written: list[Path] = []
    seen: set[Path] = set()
    for target in targets:
        key = target.expanduser()
        if key in seen:
            continue
        seen.add(key)
        try:
            key.parent.mkdir(parents=True, exist_ok=True)
            key.write_text(payload, encoding="utf-8")
            try:
                key.chmod(0o644)
            except OSError:
                pass
            # Tree .astloom should be traversable by non-root readers.
            if key.parent.name == ".astloom":
                try:
                    key.parent.chmod(0o755)
                except OSError:
                    pass
            written.append(key)
        except OSError:
            continue
    return written


def sudo_user_home() -> Path | None:
    """Home directory for ``SUDO_USER`` when install ran under sudo (best effort)."""
    user = (os.environ.get("SUDO_USER") or "").strip()
    if not user or user == "root":
        return None
    try:
        import pwd

        return Path(pwd.getpwnam(user).pw_dir)
    except (ImportError, KeyError, OSError):
        return None


def stamp_install_root_from_env(root: Path | None = None) -> list[Path]:
    """Stamp markers for *root* (or ``ASTLOOM_ROOT`` / cwd checkout)."""
    if root is None:
        env = (os.environ.get("ASTLOOM_ROOT") or "").strip()
        root = Path(env) if env else Path.cwd()
    extras: list[Path] = []
    sudo_home = sudo_user_home()
    if sudo_home is not None:
        extras.append(sudo_home)
    return stamp_install_root(root, extra_homes=extras)


