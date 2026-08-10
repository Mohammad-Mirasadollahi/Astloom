"""Stamp ``doc_version`` / ``updated_at`` on Markdown frontmatter (bulk baseline)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter

DEFAULT_DOC_VERSION = "1.0.0"


def _dump_frontmatter(data: dict[str, Any]) -> str:
    dumped = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=88,
    )
    return dumped.strip() + "\n"


def stamp_revision_frontmatter(
    text: str,
    *,
    doc_version: str = DEFAULT_DOC_VERSION,
    updated_at: str,
) -> tuple[str, bool]:
    """Set revision fields on existing YAML frontmatter.

    Returns ``(new_text, changed)``. Files without frontmatter are left unchanged.
    """
    frontmatter, body = parse_markdown_frontmatter(text)
    if not frontmatter:
        return text, False
    fm = dict(frontmatter)
    prev_version = str(fm.get("doc_version") or "").strip()
    prev_updated = str(fm.get("updated_at") or "").strip()
    target_version = str(doc_version).strip() or DEFAULT_DOC_VERSION
    target_updated = str(updated_at).strip()
    if not target_updated:
        raise ValueError("updated_at is required")
    if prev_version == target_version and prev_updated == target_updated:
        return text, False
    fm["doc_version"] = target_version
    fm["updated_at"] = target_updated
    return f"---\n{_dump_frontmatter(fm)}---\n\n{body.lstrip()}", True


def stamp_revision_tree(
    roots: list[Path],
    *,
    repo: Path,
    doc_version: str = DEFAULT_DOC_VERSION,
    updated_at: str,
    write: bool = True,
) -> dict[str, Any]:
    """Stamp all ``*.md`` under ``roots`` that already have YAML frontmatter."""
    changed: list[str] = []
    skipped_no_fm: list[str] = []
    unchanged: list[str] = []
    errors: list[str] = []
    repo = repo.resolve()
    for root in roots:
        root = root.resolve()
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            try:
                rel = str(path.resolve().relative_to(repo)).replace("\\", "/")
            except ValueError:
                rel = str(path)
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(f"{rel}: {exc}")
                continue
            new_text, did = stamp_revision_frontmatter(
                text,
                doc_version=doc_version,
                updated_at=updated_at,
            )
            fm, _ = parse_markdown_frontmatter(text)
            if not fm:
                skipped_no_fm.append(rel)
                continue
            if not did:
                unchanged.append(rel)
                continue
            if write:
                path.write_text(new_text, encoding="utf-8")
            changed.append(rel)
    return {
        "changed": changed,
        "unchanged": unchanged,
        "skipped_no_frontmatter": skipped_no_fm,
        "errors": errors,
        "summary": {
            "changed": len(changed),
            "unchanged": len(unchanged),
            "skipped_no_frontmatter": len(skipped_no_fm),
            "errors": len(errors),
            "doc_version": doc_version,
            "updated_at": updated_at,
        },
    }
