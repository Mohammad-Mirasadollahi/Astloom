"""One-shot copy from legacy Compose named volumes into Astloom-data bind dirs."""

from __future__ import annotations

import subprocess
from pathlib import Path

# compose.yaml ``name: astloom`` + volume key → docker volume name
LEGACY_VOLUME_MAP: tuple[tuple[str, str], ...] = (
    ("astloom_astloom-postgres-data", "postgres"),
    ("astloom_astloom-neo4j-data", "neo4j"),
)


def _dir_is_empty(path: Path) -> bool:
    if not path.is_dir():
        return True
    try:
        next(path.iterdir())
    except StopIteration:
        return True
    except OSError:
        return True
    return False


def _volume_exists(name: str) -> bool:
    proc = subprocess.run(
        ["docker", "volume", "inspect", name],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def migrate_named_volumes_to_data_root(data_root: Path) -> list[str]:
    """Copy legacy Docker volumes into bind dirs when those dirs are empty.

    Never deletes the source volumes. Returns list of migrated subdir names.
    """
    migrated: list[str] = []
    data_root.mkdir(parents=True, exist_ok=True)
    for volume_name, subdir in LEGACY_VOLUME_MAP:
        dest = data_root / subdir
        dest.mkdir(parents=True, exist_ok=True)
        if not _dir_is_empty(dest):
            continue
        if not _volume_exists(volume_name):
            continue
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{volume_name}:/from:ro",
                "-v",
                f"{dest.resolve()}:/to",
                "alpine:3.20",
                "sh",
                "-c",
                "cp -a /from/. /to/",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(
                f"failed to migrate Docker volume {volume_name} → {dest}: {err[:400]}"
            )
        migrated.append(subdir)
    return migrated
