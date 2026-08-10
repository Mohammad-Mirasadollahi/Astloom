"""Machine checks for Astloom documentation standards (docs 06/08/09)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter

REQUIRED_FIELDS = (
    "doc_id",
    "title",
    "doc_type",
    "status",
    "schema_version",
    "owner",
    "summary",
    "tags",
    "phase",
    "canonical_path",
)
LANE_FIELDS = (
    "lifecycle_lane",
    "concern_lane",
    "audience_lane",
    "authority",
    "visibility",
)
# Soft-required on write/edit (warnings when missing; hard issues when invalid).
REVISION_FIELDS = (
    "doc_version",
    "updated_at",
)
STATUS_OK = frozenset({"draft", "active", "deprecated", "archived"})
DOC_TYPES = frozenset(
    {
        "index",
        "standard",
        "hld",
        "lld",
        "feature_spec",
        "service_design",
        "runbook",
        "adr",
        "contract",
        "example",
        "gap",
        "glossary",
        "readme",
    }
)
DESIGN_TYPES = frozenset({"hld", "lld", "feature_spec", "service_design"})
DOC_ID_RE = re.compile(r"^as\.doc\.[a-z0-9][a-z0-9_.-]*$")
DOC_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
# ISO-8601 calendar date, optional time suffix.
UPDATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ].+)?$")
PURPOSE_H2_RE = re.compile(
    r"(?im)^##\s+(purpose|overview of|what this (document|doc)\b)",
)
H1_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")
FENCE_RE = re.compile(r"(?ms)^```.*?^```\s*$")
SOFT_BODY_LINES = 400
HARD_BODY_LINES = 800


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    return True


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().rstrip(".")).casefold()


def _body_without_fences(body: str) -> str:
    """Drop fenced code so example headings are not counted as document structure."""
    return FENCE_RE.sub("", body or "")


def check_markdown_doc(
    *,
    relative_path: str,
    text: str,
    repo: Path | None = None,
) -> dict[str, Any]:
    """Return a finding row for one Markdown file.

    When ``repo`` is set, evidence linking gaps become hard issues (sync-blocking).
    Soft body budget remains a warning — fix-on-write / quality-audit must still remediate.
    """
    issues: list[str] = []
    warnings: list[str] = []
    frontmatter, body = parse_markdown_frontmatter(text)
    prose = _body_without_fences(body)
    rel = relative_path.replace("\\", "/")

    if not frontmatter:
        issues.append("missing_or_invalid_frontmatter")
    else:
        for field in REQUIRED_FIELDS:
            if not _nonempty(frontmatter.get(field)):
                issues.append(f"missing_required:{field}")
        for field in LANE_FIELDS:
            if not _nonempty(frontmatter.get(field)):
                issues.append(f"missing_lane:{field}")
        doc_id = str(frontmatter.get("doc_id") or "").strip()
        if doc_id and not DOC_ID_RE.match(doc_id):
            issues.append("invalid_doc_id_format")
        status = str(frontmatter.get("status") or "").strip()
        if status and status not in STATUS_OK:
            issues.append("invalid_status")
        doc_type = str(frontmatter.get("doc_type") or "").strip()
        if doc_type and doc_type not in DOC_TYPES:
            issues.append("invalid_doc_type")
        tags = frontmatter.get("tags")
        if tags is not None and not isinstance(tags, list):
            issues.append("tags_must_be_list")
        canonical = str(frontmatter.get("canonical_path") or "").strip().replace("\\", "/")
        if canonical and canonical != rel:
            issues.append("canonical_path_mismatch")

        doc_version = str(frontmatter.get("doc_version") or "").strip()
        if not doc_version:
            warnings.append("missing_recommended:doc_version")
        elif not DOC_VERSION_RE.match(doc_version):
            issues.append("invalid_doc_version")

        updated_at = str(frontmatter.get("updated_at") or "").strip()
        if not updated_at:
            warnings.append("missing_recommended:updated_at")
        elif not UPDATED_AT_RE.match(updated_at):
            issues.append("invalid_updated_at")

        h1s = H1_RE.findall(prose)
        if len(h1s) == 0:
            issues.append("missing_h1")
        elif len(h1s) > 1:
            issues.append("multiple_h1")
        else:
            title = str(frontmatter.get("title") or "")
            if title and _normalize_title(title) != _normalize_title(h1s[0]):
                issues.append("title_h1_mismatch")

        if not PURPOSE_H2_RE.search(prose):
            issues.append("missing_purpose_h2")

        body_lines = len(body.splitlines())
        if body_lines > HARD_BODY_LINES:
            issues.append(f"body_over_hard_budget:{body_lines}")
        elif body_lines > SOFT_BODY_LINES:
            warnings.append(f"body_over_soft_budget:{body_lines}")

        if doc_type in DESIGN_TYPES and "```mermaid" not in body.lower():
            issues.append("design_missing_mermaid")

        # Evidence linking: cited on-disk code paths must appear in linked_symbols (hard).
        if repo is not None:
            try:
                from astloom_cli.docs_link_suggest import extract_evidence_link_tokens

                existing = {
                    str(x).strip()
                    for x in (frontmatter.get("linked_symbols") or [])
                    if isinstance(frontmatter.get("linked_symbols"), list) and str(x).strip()
                }
                cited = extract_evidence_link_tokens(body, repo=repo, max_tokens=64)
                missing = [t for t in cited if t not in existing]
                if cited and (not existing or missing):
                    issues.append(
                        "missing_linked_symbols"
                        if not existing
                        else f"missing_linked_symbols:{len(missing)}"
                    )
            except Exception:  # noqa: BLE001 — check must stay resilient
                pass

    ok = len(issues) == 0
    return {
        "file": rel,
        "ok": ok,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "issues": issues,
        "warnings": warnings,
        "doc_id": str((frontmatter or {}).get("doc_id") or "") or None,
        "doc_type": str((frontmatter or {}).get("doc_type") or "") or None,
        "status": str((frontmatter or {}).get("status") or "") or None,
        "doc_version": str((frontmatter or {}).get("doc_version") or "") or None,
        "updated_at": str((frontmatter or {}).get("updated_at") or "") or None,
    }


def check_file(path: Path, *, root: Path) -> dict[str, Any]:
    rel = str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    text = path.read_text(encoding="utf-8")
    return check_markdown_doc(relative_path=rel, text=text, repo=root)
