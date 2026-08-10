"""Import archives/hackathon/scripts/pack_paths from tests/ tree (or legacy roots)."""

from __future__ import annotations

import sys
from pathlib import Path

_SUPPORT = Path(__file__).resolve().parent
_TESTS_ROOT = _SUPPORT.parent
_REPO_ROOT = _TESTS_ROOT.parent


def _hackathon_scripts_dir() -> Path:
    for pack in (
        _REPO_ROOT / "archives" / "hackathon",
        _REPO_ROOT / "hackathon",
        _REPO_ROOT,
    ):
        scripts = pack / "scripts"
        if (scripts / "pack_paths.py").is_file():
            return scripts
    raise SystemExit(
        f"Cannot find hackathon scripts/pack_paths.py from repo root {_REPO_ROOT}"
    )


_scripts = _hackathon_scripts_dir()
_scripts_str = str(_scripts)
if _scripts_str not in sys.path:
    sys.path.insert(0, _scripts_str)

from pack_paths import (  # noqa: E402
    apply_pythonpath,
    backend_src,
    init_script,
    pack_root,
    pytest_dir,
    python_bin,
    pythonpath_entries,
    sdk_python,
    venv_base,
)

__all__ = [
    "apply_pythonpath",
    "backend_src",
    "init_script",
    "pack_root",
    "pytest_dir",
    "python_bin",
    "pythonpath_entries",
    "sdk_python",
    "venv_base",
]
