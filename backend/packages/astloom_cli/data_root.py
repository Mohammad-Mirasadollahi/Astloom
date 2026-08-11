"""Sibling data root for durable Astloom runtime data.

Module contract:
- Role: resolve and create ``<install>-data`` (or ``ASTLOOM_DATA_ROOT``) layout;
  stamp ``.astloom/data-root`` for operator inspection; migrate legacy in-tree
  durable dirs once.
- SoT / invariants: durable DB/usage/cache/backup live under data root;
  lightweight ``.astloom`` identity/upgrade/run stays under the install tree.
- Failures: never invent paths under Docker volume storage; mkdir/stamp/migrate
  are best-effort via ``ensure_data_root``.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

DATA_SUBDIRS: tuple[str, ...] = (
    "postgres",
    "neo4j",
    "backup",
    "cache",
    "mcp-usage",
    "sync-usage",
)

# Formerly under ``<install>/.astloom/`` — moved into the data root.
LEGACY_IN_TREE_SUBDIRS: tuple[str, ...] = (
    "backup",
    "cache",
    "mcp-usage",
    "sync-usage",
)

ENV_DATA_ROOT = "ASTLOOM_DATA_ROOT"
DATA_ROOT_MARKER = "data-root"


def default_data_root(install_root: Path | str) -> Path:
    """``/opt/Astloom`` → ``/opt/Astloom-data``."""
    root = Path(install_root)
    return root.parent / f"{root.name}-data"


def resolve_data_root(
    *,
    install_root: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    """Prefer ``ASTLOOM_DATA_ROOT``, else marker file, else sibling ``<basename>-data``."""
    env = environ if environ is not None else os.environ
    raw = str(env.get(ENV_DATA_ROOT) or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    if install_root is None:
        from astloom_cli.util import repo_root

        install_root = repo_root()
    marked = read_data_root_marker(install_root)
    if marked is not None:
        return marked
    return default_data_root(install_root).resolve()


def data_root_marker_path(install_root: Path | str) -> Path:
    return Path(install_root).expanduser().resolve() / ".astloom" / DATA_ROOT_MARKER


def read_data_root_marker(install_root: Path | str) -> Path | None:
    path = data_root_marker_path(install_root)
    try:
        if not path.is_file():
            return None
        line = path.read_text(encoding="utf-8").splitlines()[0].strip()
    except OSError:
        return None
    if not line:
        return None
    candidate = Path(line).expanduser()
    try:
        return candidate.resolve()
    except OSError:
        return candidate


def stamp_data_root(install_root: Path | str, data_root: Path | str) -> Path:
    """Write ``<install>/.astloom/data-root`` (absolute path, mode 0644)."""
    install = Path(install_root).expanduser().resolve()
    payload = f"{Path(data_root).expanduser().resolve()}\n"
    marker = data_root_marker_path(install)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(payload, encoding="utf-8")
    try:
        marker.chmod(0o644)
        marker.parent.chmod(0o755)
    except OSError:
        pass
    return marker


def _dir_nonempty(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        next(path.iterdir())
    except StopIteration:
        return False
    except OSError:
        return False
    return True


def migrate_legacy_in_tree_dirs(install_root: Path | str, data_root: Path | str) -> list[str]:
    """Copy nonempty ``.astloom/{backup,cache,…}`` into data root when dest empty."""
    install = Path(install_root).expanduser().resolve()
    dest_root = Path(data_root).expanduser().resolve()
    moved: list[str] = []
    for name in LEGACY_IN_TREE_SUBDIRS:
        src = install / ".astloom" / name
        dest = dest_root / name
        if not _dir_nonempty(src):
            continue
        if _dir_nonempty(dest):
            continue
        dest.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            target = dest / child.name
            if target.exists():
                continue
            if child.is_dir():
                shutil.copytree(child, target, dirs_exist_ok=True)
            else:
                shutil.copy2(child, target)
        moved.append(name)
    return moved


def ensure_data_root(
    *,
    install_root: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    """Create data-root subdirs, stamp marker, migrate legacy in-tree dirs.

    When ``ASTLOOM_DATA_ROOT`` is set, use that path for this process but **do not**
    rewrite ``<install>/.astloom/data-root``. Test shells and one-off overrides
    must not poison the durable dogfood marker.
    """
    if install_root is None:
        from astloom_cli.util import repo_root

        install_root = repo_root()
    env = environ if environ is not None else os.environ
    root = resolve_data_root(install_root=install_root, environ=env)
    root.mkdir(parents=True, exist_ok=True)
    for name in DATA_SUBDIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    if not str(env.get(ENV_DATA_ROOT) or "").strip():
        stamp_data_root(install_root, root)
        migrate_legacy_in_tree_dirs(install_root, root)
    return root


def postgres_data_dir(
    *,
    install_root: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    return resolve_data_root(install_root=install_root, environ=environ) / "postgres"


def neo4j_data_dir(
    *,
    install_root: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    return resolve_data_root(install_root=install_root, environ=environ) / "neo4j"


def backup_dir(
    *,
    install_root: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    return resolve_data_root(install_root=install_root, environ=environ) / "backup"


def cache_dir(
    *,
    install_root: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    return resolve_data_root(install_root=install_root, environ=environ) / "cache"


def mcp_usage_dir(
    *,
    install_root: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    return resolve_data_root(install_root=install_root, environ=environ) / "mcp-usage"


def sync_usage_dir(
    *,
    install_root: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    return resolve_data_root(install_root=install_root, environ=environ) / "sync-usage"

