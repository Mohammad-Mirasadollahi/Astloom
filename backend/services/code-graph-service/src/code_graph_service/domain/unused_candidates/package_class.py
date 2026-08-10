"""Classify shared-package zombies: wire / keep_public / retire.

Role: split ``backend/packages/`` findings that look like unused contracts from
true orphan packages and published SDK surfaces.
SoT: path under ``backend/packages/`` + optional disk signals (tests/profiles).
Allowed: soft recommendation only; never ``safe_to_delete``.
Forbidden: treating published SDK lanes as retire; inventing service imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Top-level dirs under backend/packages published for external/SDK use.
PUBLISHED_PACKAGE_TOPS = frozenset(
    {
        "adapter_harness",
        "astloom_sdk",
        "sdk",
    }
)


@dataclass(frozen=True)
class PackageFindingClass:
    finding_kind: str
    recommendation: str  # wire | keep_public | retire


def shared_package_top(pkg_path: str) -> str | None:
    """Return top-level ``backend/packages/<top>`` segment, else None."""
    parts = (pkg_path or "").replace("\\", "/").split("/")
    try:
        idx = parts.index("packages")
    except ValueError:
        return None
    if idx < 1 or parts[idx - 1] != "backend":
        return None
    if idx + 1 >= len(parts):
        return None
    top = parts[idx + 1].strip()
    return top or None


def _has_wire_signals(repo_root: Path, top: str) -> bool:
    underscore = top.replace("-", "_")
    test_candidates = (
        repo_root / "tests" / "backend" / "packages" / f"test_{underscore}.py",
        repo_root / "tests" / "backend" / "packages" / underscore / f"test_{underscore}.py",
    )
    if any(path.is_file() for path in test_candidates):
        return True
    profile_dirs = (
        repo_root / "backend" / "configs" / f"{top}-profiles",
        repo_root / "backend" / "configs" / f"{underscore}-profiles",
    )
    if any(path.is_dir() for path in profile_dirs):
        return True
    return False


def classify_shared_package(
    pkg_path: str,
    *,
    repo_root: str | None = None,
) -> PackageFindingClass:
    """Map a zombie package path to finding_kind + recommendation."""
    top = shared_package_top(pkg_path)
    if top is None:
        return PackageFindingClass("zombie_package", "retire")

    if top in PUBLISHED_PACKAGE_TOPS:
        return PackageFindingClass("unwired_shared_package", "keep_public")

    root = Path(repo_root) if repo_root else None
    if root is not None and root.is_dir():
        if _has_wire_signals(root, top):
            return PackageFindingClass("unwired_shared_package", "wire")
        return PackageFindingClass("zombie_package", "retire")

    # No disk context: prefer wire over delete for shared package trees.
    return PackageFindingClass("unwired_shared_package", "wire")
