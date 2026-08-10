"""Convention-based production↔test linking (Wave 1 — TESTED_BY)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

_TEST_DIR_SEGMENTS = frozenset({"tests", "test", "spec", "specs", "__tests__"})
_TEST_FILENAME = (
    re.compile(r"^test_.*", re.IGNORECASE),
    re.compile(r".*_test\..+$", re.IGNORECASE),
    re.compile(r".*\.test\..+$", re.IGNORECASE),
    re.compile(r".*\.spec\..+$", re.IGNORECASE),
    re.compile(r".*_spec\..+$", re.IGNORECASE),
    re.compile(r".*Test\.py$"),
    re.compile(r".*Tests\.py$"),
)


@dataclass(frozen=True)
class TestLink:
    """production_qualified → test_qualified candidate pair."""

    production_name: str
    test_name: str
    reason: str


def is_test_path(path: str) -> bool:
    """Classify a path as a test location (segment-aware, conservative)."""
    if not path:
        return False
    norm = path.replace("\\", "/")
    pure = PurePosixPath(norm)
    for segment in pure.parts:
        if segment.lower() in _TEST_DIR_SEGMENTS:
            return True
    name = pure.name
    return any(pat.match(name) for pat in _TEST_FILENAME)


def stem_variants(file_path: str) -> set[str]:
    """Stems useful for matching foo.py ↔ test_foo.py / foo_test.py / foo.test.ts."""
    name = PurePosixPath(file_path.replace("\\", "/")).stem
    variants = {name}
    for prefix in ("test_", "tests_"):
        if name.lower().startswith(prefix):
            variants.add(name[len(prefix) :])
    for suffix in ("_test", "_tests", ".test", ".spec", "_spec"):
        if name.lower().endswith(suffix):
            variants.add(name[: -len(suffix)])
    # Strip Test/Tests camel suffix
    if name.endswith("Tests"):
        variants.add(name[: -len("Tests")])
    elif name.endswith("Test"):
        variants.add(name[: -len("Test")])
    return {v for v in variants if v}


def suggest_test_links(
    symbols: list[tuple[str, str, str]],
) -> list[TestLink]:
    """Suggest TESTED_BY links from (qualified_name, name, file_path) triples.

    Links production symbols to test symbols when file stems match after
    stripping test_ / _test conventions. Direction: production --TESTED_BY--> test
    (same as code-review-graph: production is source).
    """
    production: list[tuple[str, str, set[str]]] = []
    tests: list[tuple[str, str, set[str]]] = []
    for qn, name, path in symbols:
        stems = stem_variants(path)
        if is_test_path(path):
            tests.append((qn, name, stems))
        else:
            production.append((qn, name, stems))

    links: list[TestLink] = []
    seen: set[tuple[str, str]] = set()
    for prod_qn, prod_name, prod_stems in production:
        for test_qn, test_name, test_stems in tests:
            if not (prod_stems & test_stems):
                # Name-level fallback: test_login covers login
                if not (
                    test_name == f"test_{prod_name}"
                    or test_name.endswith(f"_{prod_name}")
                    or prod_name in test_name
                ):
                    continue
                reason = "name_convention"
            else:
                reason = "file_stem"
            key = (prod_qn, test_qn)
            if key in seen:
                continue
            seen.add(key)
            links.append(
                TestLink(production_name=prod_qn, test_name=test_qn, reason=reason)
            )
    return links
