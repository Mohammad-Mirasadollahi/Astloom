"""Evidence-only ``linked_symbols`` suggestions for hybrid doc↔code coverage.

Does not invent graph edges. Candidates come from path citations / ``path::Symbol``
in Markdown bodies (same evidence rules as docs-standards remediator and procedure §6).
Operators may review dry-run output via ``astloom docs-suggest-links``; ``astloom sync``
Phase 2 runs the same extractor by default, merges tokens, and creates ``DOCUMENTED_BY``
only for tokens that resolve.

Optional behaviors (all documented; none invent edges):

- ``--docs-root`` — scan a tree other than ``docs/`` (e.g. ``backend/docs``).
- ``--include-all`` — report every Markdown file scanned, even with zero suggestions.
- ``--apply`` without YAML frontmatter — skip write; report ``skipped_no_frontmatter``.
- Already-linked evidence tokens — listed under ``existing``; not re-suggested.
- Missing file on disk for a path citation — token omitted (not invented).
- Loose (non-backtick) path citations — accepted as evidence (procedure §6.2).
- Path-only citations under ``tests/`` — ignored; require explicit ``path::Symbol``.
- Sync env: ``ASTLOOM_SYNC_DOCS_EVIDENCE`` / ``ASTLOOM_SYNC_DOCS_EVIDENCE_APPLY``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter

_PATH_SYMBOL_RE = re.compile(
    r"`((?:backend|frontend|tests|scripts)/[^`\n]+?::[A-Za-z_][\w]*)`"
)
_FILE_PATH_RE = re.compile(
    r"`((?:backend|frontend|tests|scripts)/[^`\n]+?\.(?:py|ts|tsx))`"
)
_LOOSE_FILE_RE = re.compile(
    r"(?<![/\w`])((?:backend|frontend|tests|scripts)/[A-Za-z0-9_./-]+\.(?:py|ts|tsx))"
)
_PY_TOP_SYMBOL_RE = re.compile(
    r"^(?:async\s+)?def\s+([A-Za-z_][\w]*)|^class\s+([A-Za-z_][\w]*)",
    re.MULTILINE,
)


def _looks_like_test_path(path: Path) -> bool:
    parts = {p.casefold() for p in path.parts}
    name = path.name.casefold()
    return (
        "tests" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
    )


def primary_symbol_name(path: Path) -> str | None:
    """Best public top-level ``def`` / ``async def`` / ``class`` for evidence tokens.

    For test paths, prefer the first ``test_*`` function so helpers/fixtures are
    not mistaken for the documented symbol when a body only cites the file path.
    """
    if path.suffix != ".py" or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    names: list[str] = []
    for match in _PY_TOP_SYMBOL_RE.finditer(text):
        name = match.group(1) or match.group(2)
        if name and not name.startswith("_"):
            names.append(name)
    if not names:
        return None
    if _looks_like_test_path(path):
        for name in names:
            if name.startswith("test_"):
                return name
        return None
    return names[0]


def extract_evidence_link_tokens(
    body: str,
    *,
    repo: Path,
    max_tokens: int = 32,
) -> list[str]:
    """Collect ``path::Symbol`` tokens evidenced on disk; never invent names."""
    found: list[str] = []
    seen: set[str] = set()

    def add(token: str) -> None:
        text = str(token or "").strip()
        if not text or text in seen or "::" not in text:
            return
        file_path, _, name = text.partition("::")
        file_path = file_path.strip().replace("\\", "/")
        name = name.strip()
        if not file_path or not name:
            return
        if "/" in file_path and not (repo / file_path).is_file():
            return
        seen.add(text)
        found.append(text)

    def add_path(rel_path: str) -> None:
        rel = rel_path.strip().replace("\\", "/")
        # Path-only citations under tests/ are ambiguous (helpers vs cases).
        # Require explicit ``path::Symbol`` evidence for test trees.
        if rel.startswith("tests/") or "/tests/" in f"/{rel}/":
            return
        symbol = primary_symbol_name(repo / rel)
        if symbol:
            add(f"{rel}::{symbol}")

    for match in _PATH_SYMBOL_RE.finditer(body or ""):
        add(match.group(1))
    for match in _FILE_PATH_RE.finditer(body or ""):
        add_path(match.group(1))
    for match in _LOOSE_FILE_RE.finditer(body or ""):
        add_path(match.group(1))
    return found[:max_tokens]


def suggest_links_for_markdown(
    *,
    relative_path: str,
    text: str,
    repo: Path,
) -> dict[str, Any]:
    """Diff evidence tokens vs existing frontmatter ``linked_symbols``."""
    fm, body = parse_markdown_frontmatter(text)
    has_frontmatter = bool(fm)
    existing = [
        str(x).strip()
        for x in ((fm or {}).get("linked_symbols") or [])
        if str(x).strip()
    ]
    evidence = extract_evidence_link_tokens(body, repo=repo)
    existing_set = set(existing)
    missing = [t for t in evidence if t not in existing_set]
    already_linked = [t for t in evidence if t in existing_set]
    return {
        "file": relative_path.replace("\\", "/"),
        "has_frontmatter": has_frontmatter,
        "existing_count": len(existing),
        "evidence_count": len(evidence),
        "suggested_new": missing,
        "already_linked": already_linked,
        "evidence": evidence,
        "existing": existing,
        "mode": "hybrid_evidence_suggest",
        "note": (
            "Suggestions are evidence-only. Apply to frontmatter and/or run "
            "astloom sync Phase 2 (evidence merge default); unresolved tokens "
            "never create edges. Apply skips files without YAML frontmatter."
        ),
    }


def suggest_links_for_tree(
    repo: Path,
    *,
    docs_root: str = "docs",
    include_all: bool = False,
) -> dict[str, Any]:
    root = (repo / docs_root).resolve()
    rows: list[dict[str, Any]] = []
    scanned = 0
    if not root.is_dir():
        return {
            "repo": str(repo),
            "docs_root": docs_root,
            "files": [],
            "scanned_count": 0,
            "files_with_suggestions": 0,
            "suggested_total": 0,
            "mode": "hybrid_evidence_suggest",
        }
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        scanned += 1
        rel = str(path.relative_to(repo)).replace("\\", "/")
        text = path.read_text(encoding="utf-8", errors="replace")
        row = suggest_links_for_markdown(relative_path=rel, text=text, repo=repo)
        if include_all or row["suggested_new"]:
            rows.append(row)
    with_suggestions = [r for r in rows if r.get("suggested_new")]
    return {
        "repo": str(repo.resolve()),
        "docs_root": docs_root,
        "mode": "hybrid_evidence_suggest",
        "scanned_count": scanned,
        "files_with_suggestions": len(with_suggestions),
        "suggested_total": sum(len(r["suggested_new"]) for r in with_suggestions),
        "include_all": include_all,
        "files": rows,
    }


def apply_suggested_links(path: Path, new_tokens: list[str]) -> dict[str, Any]:
    """Merge tokens into frontmatter. Skips when YAML frontmatter is absent."""
    from astloom_cli.commands.docs_standards.remediate import _dump_frontmatter

    text = path.read_text(encoding="utf-8")
    fm, body = parse_markdown_frontmatter(text)
    rel = str(path)
    if not fm:
        return {
            "file": rel,
            "status": "skipped_no_frontmatter",
            "added": [],
        }
    if not new_tokens:
        return {"file": rel, "status": "noop", "added": []}
    existing = [
        str(x).strip()
        for x in (fm.get("linked_symbols") or [])
        if str(x).strip()
    ]
    merged = list(existing)
    seen = set(existing)
    added: list[str] = []
    for token in new_tokens:
        if token not in seen:
            merged.append(token)
            seen.add(token)
            added.append(token)
    if not added:
        return {"file": rel, "status": "noop", "added": []}
    fm["linked_symbols"] = merged
    path.write_text(f"---\n{_dump_frontmatter(fm)}---\n\n{body.lstrip()}", encoding="utf-8")
    return {"file": rel, "status": "applied", "added": added}
