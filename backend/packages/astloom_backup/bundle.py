"""Pack/unpack .asbak archives (gzip tar)."""

from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path


def pack_directory(src_dir: Path, dest_asbak: Path) -> Path:
    dest_asbak.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest_asbak, "w:gz") as tar:
        for path in sorted(src_dir.rglob("*")):
            if path.is_file():
                tar.add(path, arcname=path.relative_to(src_dir).as_posix())
    return dest_asbak


def unpack_archive(asbak: Path, dest_dir: Path | None = None) -> Path:
    if not asbak.is_file():
        raise FileNotFoundError(f"bundle not found: {asbak}")
    out = dest_dir or Path(tempfile.mkdtemp(prefix="asbak-"))
    out.mkdir(parents=True, exist_ok=True)
    with tarfile.open(asbak, "r:gz") as tar:
        # Python 3.12+ filter for path traversal safety when available.
        try:
            tar.extractall(out, filter="data")
        except TypeError:
            tar.extractall(out)
    return out
