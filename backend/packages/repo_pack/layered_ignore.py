"""Layered ignore: defaults → .gitignore → .astloomignore (CI-45 / RM-05)."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

IGNORE_FILENAMES = (".gitignore", ".astloomignore")


@dataclass(frozen=True)
class IgnoreRule:
    pattern: str
    negate: bool = False


def _normalize_glob(pattern: str) -> str:
    return pattern.strip().replace("\\", "/").lstrip("./")


def path_matches_glob(relative_path: str, pattern: str) -> bool:
    rel = relative_path.replace("\\", "/").lstrip("./")
    pat = _normalize_glob(pattern)
    if not pat:
        return False
    candidates = [pat]
    if pat.startswith("**/"):
        candidates.append(pat[3:])
    if pat.endswith("/**"):
        candidates.append(pat[:-3].rstrip("/"))
    for candidate in candidates:
        if not candidate:
            continue
        if fnmatch.fnmatch(rel, candidate):
            return True
        if fnmatch.fnmatch(Path(rel).name, candidate):
            return True
    if "*" not in pat and "?" not in pat and "[" not in pat and "/" not in pat:
        return any(part.lower() == pat.lower() for part in Path(rel).parts)
    return False


def _normalize_pattern_line(line: str) -> str:
    text = line.replace("\\", "/").lstrip("./")
    if text.endswith("/"):
        text = text.rstrip("/") + "/**"
    return text


def load_ignore_rules(path: Path) -> list[IgnoreRule]:
    """Parse gitignore-style rules (supports ``!`` negation; last match wins)."""
    if not path.is_file():
        return []
    out: list[IgnoreRule] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negate = False
        if line.startswith("!"):
            negate = True
            line = line[1:].strip()
            if not line:
                continue
        out.append(IgnoreRule(pattern=_normalize_pattern_line(line), negate=negate))
    return out


def load_ignore_file_patterns(path: Path) -> list[str]:
    """Positive exclude globs only (legacy helper)."""
    return [r.pattern for r in load_ignore_rules(path) if not r.negate]


def collect_layered_ignore_rules(root: Path) -> tuple[list[IgnoreRule], list[str]]:
    """Ordered rules from ``.gitignore`` then ``.astloomignore``."""
    root = root.expanduser().resolve()
    rules: list[IgnoreRule] = []
    sources: list[str] = []
    for name in IGNORE_FILENAMES:
        path = root / name
        loaded = load_ignore_rules(path)
        if not loaded:
            continue
        sources.append(str(path))
        rules.extend(loaded)
    return rules, sources


def collect_layered_ignore_globs(root: Path) -> tuple[list[str], list[str]]:
    """Return (positive exclude globs, source_paths) for sync filter merge."""
    rules, sources = collect_layered_ignore_rules(root)
    seen: set[str] = set()
    globs: list[str] = []
    for rule in rules:
        if rule.negate:
            continue
        if rule.pattern in seen:
            continue
        seen.add(rule.pattern)
        globs.append(rule.pattern)
    return globs, sources


def collect_layered_reinclude_globs(root: Path) -> list[str]:
    """Patterns from ``!`` lines (force-include after exclude match)."""
    rules, _ = collect_layered_ignore_rules(root)
    seen: set[str] = set()
    out: list[str] = []
    for rule in rules:
        if not rule.negate:
            continue
        if rule.pattern in seen:
            continue
        seen.add(rule.pattern)
        out.append(rule.pattern)
    return out


def path_is_ignored(
    relative_path: str,
    patterns: list[str] | None = None,
    *,
    rules: list[IgnoreRule] | None = None,
) -> bool:
    """True when path should be skipped.

    Prefer ``rules`` (last matching rule wins, including ``!`` negation).
    ``patterns`` is positive-only (any match → ignored).
    """
    rel = relative_path.replace("\\", "/").lstrip("./")
    if rules is not None:
        ignored = False
        for rule in rules:
            if path_matches_glob(rel, rule.pattern):
                ignored = not rule.negate
        return ignored
    return any(path_matches_glob(rel, p) for p in (patterns or []) if p)
