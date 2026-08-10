"""Remediate Markdown docs to pass ``docs-standards`` machine checks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from astloom_cli.commands.docs_standards.check import (
    DESIGN_TYPES,
    DOC_ID_RE,
    DOC_TYPES,
    DOC_VERSION_RE,
    H1_RE,
    PURPOSE_H2_RE,
    STATUS_OK,
    check_markdown_doc,
)
from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter
from astloom_cli.util import now_iso

_STATUS_MAP = {
    "proposed": "draft",
    "accepted": "active",
    "rejected": "archived",
    "superseded": "archived",
    "withdrawn": "archived",
    "experimental": "draft",
    "stable": "active",
}

_DOC_TYPE_MAP = {
    "design": "hld",
    "feature": "feature_spec",
    "feature-specification": "feature_spec",
    "high-level-design": "hld",
    "low-level-design": "lld",
    "specification": "standard",
    "guide": "standard",
    "onboarding": "runbook",
    "roadmap": "gap",
    "risks": "gap",
    "risks-acceptance": "gap",
    "contracts": "contract",
    "policy": "standard",
    "readme": "readme",
}

_CONCERN_MAP = {
    "feature": "product",
    "feature-specification": "product",
    "risks": "problem",
    "risk": "problem",
    "risks-acceptance": "problem",
    "specification": "standard",
    "guide": "standard",
    "onboarding": "onboarding",
    "contracts": "contract",
    "high-level-design": "design",
    "low-level-design": "design",
    "roadmap": "gap",
    "implementation": "design",
    "architecture": "design",
    "integration": "cross_team",
    "runbook": "ops",
}

_VALID_CONCERNS = frozenset(
    {
        "standard",
        "design",
        "decision",
        "problem",
        "gap",
        "contract",
        "ops",
        "example",
        "cross_team",
        "onboarding",
        "security",
        "product",
    }
)

_PHASE_SLUG = {
    "00-master-plan": "master",
    "01-core-data-model": "core",
    "02-memory-and-context": "memory",
    "03-docs-as-code-sync": "docs-sync",
    "04-rule-engine-orchestration": "rules",
    "05-interoperability-ecosystem": "interop",
    "06-technical-logic": "tech",
    "07-code-knowledge-graph": "ckg",
    "08-software-engineering-architecture": "sea",
    "09-platform-governance-operations": "ops",
    "10-gap-analysis": "gap",
    "11-logical-implementation-examples": "examples",
    "12-common-context-reuse": "common-context",
    "13-technology-stack-and-platform-decisions": "stack",
    "14-api-design-and-naming-standards": "api",
    "15-agent-workspace-guidance": "awg",
    "agents": "agents",
}

_CURATED_DOC_LINKS: dict[str, list[str]] = {
    "docs/07-code-knowledge-graph/03-ingestion-and-living-documentation-workflow.md": [
        "backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs",
        "backend/services/code-graph-service/src/code_graph_service/application/ingest/human_docs.py::HumanDocIngestMixin",
        "backend/services/code-graph-service/src/code_graph_service/domain/symbol_resolve.py::resolve_linked_symbol",
        "backend/services/code-graph-service/src/code_graph_service/domain/doc_discovery.py::discover_documentation_files",
    ],
    "docs/03-docs-as-code-sync/00-index.md": [
        "backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs",
        "backend/services/code-graph-service/src/code_graph_service/application/ingest/human_docs.py::HumanDocIngestMixin",
    ],
    "docs/03-docs-as-code-sync/01-feature-specification.md": [
        "backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs",
        "backend/services/code-graph-service/src/code_graph_service/domain/doc_discovery.py::discover_documentation_files",
    ],
    "docs/08-software-engineering-architecture/36-astloom-cli.md": [
        "backend/packages/astloom_cli/main.py::main",
        "backend/packages/astloom_cli/commands/sync.py::cmd_sync",
        "backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs",
    ],
    "docs/08-software-engineering-architecture/42-astloom-cli-command-reference.md": [
        "backend/packages/astloom_cli/main.py::main",
        "backend/packages/astloom_cli/commands/sync.py::cmd_sync",
        "backend/packages/astloom_cli/commands/docs_standards/cmd.py::cmd_docs_standards",
        "backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs",
        "backend/packages/astloom_cli/commands/docs_standards/remediate.py::remediate_markdown_doc",
    ],
    "docs/00-master-plan/08-documentation-structure-and-machine-ingest-standard.md": [
        "backend/packages/astloom_cli/commands/docs_standards/check.py::check_markdown_doc",
        "backend/packages/astloom_cli/commands/docs_standards/remediate.py::remediate_markdown_doc",
        "backend/packages/astloom_cli/markdown_frontmatter.py::parse_markdown_frontmatter",
    ],
    "docs/00-master-plan/09-documentation-classification-and-lanes.md": [
        "backend/packages/astloom_cli/commands/docs_standards/check.py::check_markdown_doc",
    ],
    "docs/00-master-plan/10-documentation-standardization-procedure.md": [
        "backend/packages/astloom_cli/commands/docs_standards/check.py::check_markdown_doc",
        "backend/packages/astloom_cli/commands/docs_standards/remediate.py::remediate_markdown_doc",
        "backend/packages/astloom_cli/commands/docs_standards/collect.py::build_docs_standards_report",
        "backend/packages/astloom_cli/commands/docs_standards/cmd.py::cmd_docs_standards",
        "backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs",
    ],
    "docs/agents/documentation-authoring.md": [
        "backend/packages/astloom_cli/commands/docs_standards/check.py::check_markdown_doc",
        "backend/packages/astloom_cli/commands/docs_standards/remediate.py::remediate_markdown_doc",
    ],
}

_MERMAID_BLOCK = """## Document flow

```mermaid
flowchart TD
  reader[Reader] --> doc[This document]
  doc --> next[Related docs or implementation]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Reader | Opens this design document | Understands scope and constraints |
| 2 | Reader | Follows the Mermaid flow | Sees primary component interactions |
| 3 | Reader | Uses Related Documents / linked symbols | Reaches deeper design or implementation |
"""

_FLOW_TABLE_RE = re.compile(r"(?im)^\|.+\b(step|actor|action|outcome)\b.+\|")
_MERMAID_FENCE_RE = re.compile(r"(?is)```mermaid.*?```")
_FLOW_TABLE_ONLY = """
| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Reader | Opens this design document | Understands scope and constraints |
| 2 | Reader | Follows the Mermaid flow | Sees primary component interactions |
| 3 | Reader | Uses Related Documents / linked symbols | Reaches deeper design or implementation |
"""


def _utc_date() -> str:
    """Calendar date (UTC) for ``updated_at``."""
    return now_iso()[:10]


def _normalize_doc_version(raw: str | None) -> str:
    text = str(raw or "").strip()
    if text and DOC_VERSION_RE.match(text):
        return text
    return "1.0.0"


def _bump_patch_version(raw: str) -> str:
    parts = str(raw or "").strip().split(".")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return f"{int(parts[0])}.{int(parts[1])}.{int(parts[2]) + 1}"
    return "1.0.0"


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").casefold()).strip("-")
    return s or "doc"


def _infer_doc_type(rel: str, stem: str, existing: str | None) -> str:
    if existing and existing in DOC_TYPES:
        return existing
    mapped = _DOC_TYPE_MAP.get((existing or "").strip().casefold())
    if mapped:
        return mapped
    name = stem.casefold()
    if stem == "README" or rel.endswith("/README.md") or rel == "docs/README.md":
        return "readme"
    if name.startswith("00-index") or name == "00-index":
        return "index"
    if "feature-specification" in name or name.endswith("-feature-spec"):
        return "feature_spec"
    if "high-level-design" in name or name.endswith("-hld"):
        return "hld"
    if "low-level-design" in name or name.endswith("-lld"):
        return "lld"
    if name.endswith("-adr") or "-adr-" in name or name.startswith("adr-"):
        return "adr"
    if "runbook" in name:
        return "runbook"
    if "contract" in name or "data-contracts" in name:
        return "contract"
    if "glossary" in name:
        return "glossary"
    if "gap" in name or "risk" in name:
        return "gap"
    if "example" in name or "checklist" in name:
        return "example"
    if "standard" in name or "policy" in name or "naming" in name:
        return "standard"
    if "service-design" in name:
        return "service_design"
    return "standard"


def _infer_status(rel: str, existing: str | None, doc_type: str) -> str:
    raw = (existing or "").strip().casefold()
    if raw in STATUS_OK:
        return raw
    if raw in _STATUS_MAP:
        return _STATUS_MAP[raw]
    if "gap-analysis" in rel or doc_type == "gap":
        return "draft"
    if doc_type in {"feature_spec", "hld", "lld", "example"}:
        return "draft"
    return "active"


def _infer_lanes(rel: str, doc_type: str, status: str) -> dict[str, Any]:
    if "gap-analysis" in rel or doc_type == "gap":
        lifecycle = "future" if status == "draft" else "current"
        concern = "gap"
    elif doc_type == "adr":
        lifecycle = "current"
        concern = "decision"
    elif doc_type in DESIGN_TYPES:
        lifecycle = "future" if status == "draft" else "current"
        concern = "design"
    elif doc_type == "contract":
        lifecycle = "current"
        concern = "contract"
    elif doc_type == "runbook":
        lifecycle = "current"
        concern = "ops"
    elif doc_type == "example":
        lifecycle = "current"
        concern = "example"
    elif doc_type in {"index", "readme"}:
        lifecycle = "current"
        concern = "onboarding"
    elif "security" in rel or "threat" in rel:
        lifecycle = "current"
        concern = "security"
    else:
        lifecycle = "current"
        concern = "standard"

    authority = "normative" if concern in {"standard", "contract", "decision", "ops"} else "informative"
    return {
        "lifecycle_lane": lifecycle,
        "concern_lane": concern,
        "audience_lane": ["platform-engineering", "agents"],
        "authority": authority,
        "visibility": "internal",
    }


def _phase_from_rel(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    if len(parts) >= 2 and parts[0] == "docs":
        folder = parts[1]
        if folder.endswith(".md"):
            return "docs"
        return folder
    return "docs"


def _domain_from_rel(rel: str) -> str:
    phase = _phase_from_rel(rel)
    return _PHASE_SLUG.get(phase, _slugify(phase))


def _make_doc_id(rel: str, stem: str, existing: str | None) -> str:
    raw = (existing or "").strip()
    if raw.startswith("tsoc.doc."):
        raw = "as.doc." + raw[len("tsoc.doc.") :]
    if DOC_ID_RE.match(raw):
        return raw
    domain = _domain_from_rel(rel)
    slug = _slugify(re.sub(r"^\d+-", "", stem))
    candidate = f"as.doc.{domain}.{slug}"
    if not DOC_ID_RE.match(candidate):
        candidate = f"as.doc.{_slugify(domain)}.{_slugify(slug)}"
    return candidate


def _first_prose_sentence(body: str) -> str:
    prose = re.sub(r"(?ms)^```.*?^```\s*$", "", body or "")
    prose = re.sub(r"(?m)^#+\s+.*$", "", prose)
    for para in re.split(r"\n\s*\n", prose.strip()):
        line = " ".join(para.split())
        if len(line) < 40:
            continue
        sentence = re.match(r"(.+?[.!?])(\s|$)", line)
        if sentence and len(sentence.group(1)) >= 40:
            return sentence.group(1).strip()
        if len(line) <= 400:
            return line.rstrip(".,;:") + "."
        cut = line[:400].rsplit(" ", 1)[0].rstrip(".,;:")
        return (cut or line[:400]).rstrip(".,;:") + "."
    return "This document describes Astloom design and operating guidance for its topic area."


def _heal_summary(existing: str, body: str) -> str:
    """Prefer a complete first-sentence summary when the stored one looks truncated."""
    full = _first_prose_sentence(body)
    current = (existing or "").strip()
    if not current:
        return full
    cur_core = current.rstrip(".,;:")
    full_core = full.rstrip(".,;:")
    if cur_core == full_core:
        return current if current.endswith((".", "!", "?")) else full
    if full_core.startswith(cur_core) and len(full_core) > len(cur_core) + 5:
        return full
    last = cur_core.split()[-1] if cur_core.split() else ""
    if len(last) <= 4 or last in {"prod", "arch", "engin", "softw", "platf"}:
        return full
    if not current.endswith((".", "!", "?")):
        return full
    return current


def _ensure_single_h1(body: str, title: str) -> str:
    matches = list(H1_RE.finditer(body))
    if not matches:
        return f"# {title}\n\n{body.lstrip()}"
    # Keep first H1; demote later H1s to H2.
    out = body
    # Work from the end so offsets stay valid.
    for match in reversed(matches[1:]):
        out = out[: match.start()] + "## " + match.group(1).strip() + out[match.end() :]
    first = H1_RE.search(out)
    if first and first.group(1).strip() != title:
        out = out[: first.start()] + f"# {title}" + out[first.end() :]
    return out


def _ensure_purpose(body: str, summary: str) -> str:
    prose = re.sub(r"(?ms)^```.*?^```\s*$", "", body)
    if PURPOSE_H2_RE.search(prose):
        return body
    purpose = (
        f"## Purpose\n\n{summary.strip()}\n\n"
        if summary.strip()
        else "## Purpose\n\nThis document owns its listed topic for Astloom authors and agents.\n\n"
    )
    match = H1_RE.search(body)
    if not match:
        return purpose + body
    insert_at = match.end()
    # Skip blank lines after H1.
    while insert_at < len(body) and body[insert_at] == "\n":
        insert_at += 1
    return body[:insert_at] + "\n" + purpose + body[insert_at:]


def _ensure_mermaid(body: str, doc_type: str) -> str:
    if doc_type not in DESIGN_TYPES:
        return body
    out = body
    if "```mermaid" not in out.lower():
        purpose = PURPOSE_H2_RE.search(out)
        if purpose:
            rest = out[purpose.end() :]
            next_h = re.search(r"(?m)^##\s+", rest)
            if next_h:
                at = purpose.end() + next_h.start()
                out = out[:at] + _MERMAID_BLOCK + "\n" + out[at:]
            else:
                match = H1_RE.search(out)
                if match:
                    at = match.end()
                    while at < len(out) and out[at] == "\n":
                        at += 1
                    out = out[:at] + "\n" + _MERMAID_BLOCK + "\n" + out[at:]
                else:
                    out = _MERMAID_BLOCK + "\n" + out
        else:
            match = H1_RE.search(out)
            if match:
                at = match.end()
                while at < len(out) and out[at] == "\n":
                    at += 1
                out = out[:at] + "\n" + _MERMAID_BLOCK + "\n" + out[at:]
            else:
                out = _MERMAID_BLOCK + "\n" + out
    elif not _FLOW_TABLE_RE.search(out):
        mermaid = _MERMAID_FENCE_RE.search(out)
        if mermaid:
            at = mermaid.end()
            out = out[:at] + "\n" + _FLOW_TABLE_ONLY + out[at:]
    return out


def _normalize_concern(raw: str, fallback: str) -> str:
    value = (raw or "").strip()
    mapped = _CONCERN_MAP.get(value.casefold(), value)
    if mapped in _VALID_CONCERNS:
        return mapped
    if fallback in _VALID_CONCERNS:
        return fallback
    return "standard"


def _extract_linked_symbols(
    body: str,
    *,
    repo: Path,
    existing: list[Any] | None,
) -> list[str]:
    """Collect evidence-based ``path::Symbol`` tokens; never invent unrelated edges."""
    from astloom_cli.docs_link_suggest import extract_evidence_link_tokens

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

    for item in existing or []:
        add(str(item))
    for token in extract_evidence_link_tokens(body, repo=repo, max_tokens=32):
        add(token)
    return found[:24]


def _links_for_doc(rel: str, body: str, *, repo: Path, existing: list[Any] | None) -> list[str]:
    seeded = list(existing or [])
    seeded.extend(_CURATED_DOC_LINKS.get(rel, []))
    return _extract_linked_symbols(body, repo=repo, existing=seeded)


def _dump_frontmatter(data: dict[str, Any]) -> str:
    # Prefer stable key order for required + lane fields first.
    ordered_keys = [
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
        "lifecycle_lane",
        "concern_lane",
        "audience_lane",
        "authority",
        "visibility",
        "doc_version",
        "updated_at",
        "linked_symbols",
    ]
    ordered: dict[str, Any] = {}
    for key in ordered_keys:
        if key in data:
            ordered[key] = data[key]
    for key, value in data.items():
        if key not in ordered:
            ordered[key] = value
    dumped = yaml.safe_dump(
        ordered,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=88,
    )
    return dumped.strip() + "\n"


def remediate_markdown_doc(
    *,
    relative_path: str,
    text: str,
    repo: Path | None = None,
) -> str:
    """Return Markdown text that should pass ``check_markdown_doc``."""
    rel = relative_path.replace("\\", "/")
    root = (repo or Path.cwd()).resolve()
    frontmatter, body = parse_markdown_frontmatter(text)
    fm: dict[str, Any] = dict(frontmatter or {})

    stem = Path(rel).stem
    h1_match = H1_RE.search(re.sub(r"(?ms)^```.*?^```\s*$", "", body))
    title = str(fm.get("title") or "").strip()
    if h1_match:
        title = h1_match.group(1).strip()
    elif not title:
        title = stem.replace("-", " ").title()

    doc_type = _infer_doc_type(rel, stem, str(fm.get("doc_type") or "") or None)
    status = _infer_status(rel, str(fm.get("status") or "") or None, doc_type)
    lanes = _infer_lanes(rel, doc_type, status)

    summary = _heal_summary(str(fm.get("summary") or "").strip(), body)

    tags = fm.get("tags")
    if not isinstance(tags, list) or not tags:
        tags = [_slugify(doc_type), _domain_from_rel(rel)]

    phase = str(fm.get("phase") or "").strip() or _phase_from_rel(rel)
    owner = str(fm.get("owner") or "").strip() or "platform-docs"

    concern = _normalize_concern(
        str(fm.get("concern_lane") or "").strip() or lanes["concern_lane"],
        lanes["concern_lane"],
    )
    existing_links = fm.get("linked_symbols") if isinstance(fm.get("linked_symbols"), list) else []
    linked_symbols = _links_for_doc(rel, body, repo=root, existing=existing_links)

    prior_version = str(fm.get("doc_version") or "").strip()
    had_valid_version = bool(prior_version and DOC_VERSION_RE.match(prior_version))
    # Remediator always touches structure/metadata → refresh revision stamp.
    doc_version = (
        _bump_patch_version(prior_version) if had_valid_version else _normalize_doc_version(prior_version)
    )

    new_fm: dict[str, Any] = {
        **fm,
        "doc_id": _make_doc_id(rel, stem, str(fm.get("doc_id") or "") or None),
        "title": title,
        "doc_type": doc_type,
        "status": status,
        "schema_version": str(fm.get("schema_version") or "1.0"),
        "owner": owner,
        "summary": summary,
        "tags": [str(t) for t in tags if str(t).strip()],
        "phase": phase,
        "canonical_path": rel,
        **{k: fm.get(k) or v for k, v in lanes.items()},
        "concern_lane": concern,
        "doc_version": doc_version,
        "updated_at": _utc_date(),
        "linked_symbols": linked_symbols,
    }
    # Force lane defaults when missing/empty.
    for key, value in lanes.items():
        if not new_fm.get(key):
            new_fm[key] = value
    new_fm["concern_lane"] = _normalize_concern(
        str(new_fm.get("concern_lane") or ""),
        lanes["concern_lane"],
    )

    body2 = _ensure_single_h1(body, title)
    body2 = _ensure_purpose(body2, summary)
    body2 = _ensure_mermaid(body2, doc_type)
    return f"---\n{_dump_frontmatter(new_fm)}---\n\n{body2.lstrip()}"


def remediate_tree(
    docs_root: Path,
    *,
    repo: Path,
    force: bool = False,
) -> dict[str, Any]:
    """Rewrite Markdown under ``docs_root`` until checks pass. Returns counts."""
    changed = 0
    failed: list[dict[str, Any]] = []
    for path in sorted(docs_root.rglob("*.md")):
        if not path.is_file():
            continue
        rel = str(path.resolve().relative_to(repo.resolve())).replace("\\", "/")
        original = path.read_text(encoding="utf-8")
        before = check_markdown_doc(relative_path=rel, text=original)
        if before["ok"] and not force:
            continue
        fixed = remediate_markdown_doc(relative_path=rel, text=original, repo=repo)
        after = check_markdown_doc(relative_path=rel, text=fixed)
        if fixed != original:
            path.write_text(fixed, encoding="utf-8")
            changed += 1
        if not after["ok"]:
            failed.append({"file": rel, "issues": after["issues"]})
    return {"changed": changed, "still_failing": failed}
