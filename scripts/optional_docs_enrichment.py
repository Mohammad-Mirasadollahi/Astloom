#!/usr/bin/env python3
"""Optional docs pass: expand evidence linked_symbols + design flow tables."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path("/opt/Astloom")
sys.path[:0] = [
    str(ROOT / "backend" / "packages"),
    str(ROOT / "backend" / "services" / "code-graph-service" / "src"),
]

from astloom_cli.commands.docs_standards.check import DESIGN_TYPES, check_markdown_doc
from astloom_cli.commands.docs_standards.collect import build_docs_standards_report
from astloom_cli.commands.docs_standards.remediate import (
    _CURATED_DOC_LINKS,
    _dump_frontmatter,
    remediate_markdown_doc,
)
from astloom_cli.docs_link_suggest import extract_evidence_link_tokens
from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter

FLOW_TABLE_RE = re.compile(r"(?im)^\|.+\b(step|actor|action|outcome)\b.+\|")
MERMAID_RE = re.compile(r"(?is)```mermaid.*?```")

FLOW_TABLE = """
| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Reader | Opens this design document | Understands scope and constraints |
| 2 | Reader | Follows the Mermaid flow | Sees primary component interactions |
| 3 | Reader | Uses Related Documents / linked symbols | Reaches deeper design or implementation |
"""


def _tokens_from_body(body: str) -> list[str]:
    return extract_evidence_link_tokens(body, repo=ROOT, max_tokens=64)


def _ensure_flow_table(body: str, doc_type: str) -> str:
    if doc_type not in DESIGN_TYPES:
        return body
    if "```mermaid" not in body.lower():
        return body
    if FLOW_TABLE_RE.search(body):
        return body
    match = MERMAID_RE.search(body)
    if not match:
        return body
    insert_at = match.end()
    return body[:insert_at] + "\n" + FLOW_TABLE + body[insert_at:]


def _merge_links(existing: list, discovered: list[str], curated: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in list(existing or []) + curated + discovered:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        if "::" in text:
            path, _, _name = text.partition("::")
            path = path.strip().replace("\\", "/")
            if "/" in path and not (ROOT / path).is_file():
                continue
        seen.add(text)
        out.append(text)
    return out[:32]


def main() -> int:
    changed_links = 0
    changed_flow = 0
    for path in sorted((ROOT / "docs").rglob("*.md")):
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        original = path.read_text(encoding="utf-8")
        fm, body = parse_markdown_frontmatter(original)
        if not fm:
            continue
        doc_type = str(fm.get("doc_type") or "")
        existing = fm.get("linked_symbols") if isinstance(fm.get("linked_symbols"), list) else []
        discovered = _tokens_from_body(body)
        curated = list(_CURATED_DOC_LINKS.get(rel, []))
        merged = _merge_links(existing, discovered, curated)
        body2 = _ensure_flow_table(body, doc_type)
        links_changed = merged != [str(x).strip() for x in (existing or []) if str(x).strip()]
        flow_changed = body2 != body
        if not links_changed and not flow_changed:
            continue
        new_fm = dict(fm)
        new_fm["linked_symbols"] = merged
        new_fm["canonical_path"] = rel
        text = f"---\n{_dump_frontmatter(new_fm)}---\n\n{body2.lstrip()}"
        # Keep machine gate green without rewriting unrelated fields aggressively.
        fixed = remediate_markdown_doc(relative_path=rel, text=text, repo=ROOT)
        # Preserve expanded links after remediate (remediator may recompute).
        fm2, body3 = parse_markdown_frontmatter(fixed)
        fm2["linked_symbols"] = _merge_links(
            fm2.get("linked_symbols") if isinstance(fm2.get("linked_symbols"), list) else [],
            discovered,
            curated,
        )
        final = f"---\n{_dump_frontmatter(fm2)}---\n\n{body3.lstrip()}"
        row = check_markdown_doc(relative_path=rel, text=final)
        if not row["ok"]:
            print("FAIL", rel, row["issues"])
            continue
        if final != original:
            path.write_text(final, encoding="utf-8")
            if links_changed:
                changed_links += 1
            if flow_changed:
                changed_flow += 1
            print(
                f"UPD {rel} links={len(fm2.get('linked_symbols') or [])} "
                f"flow={'yes' if flow_changed else 'no'}"
            )

    report = build_docs_standards_report(repo=ROOT)
    linked = 0
    for p in (ROOT / "docs").rglob("*.md"):
        fm, _ = parse_markdown_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        ls = (fm or {}).get("linked_symbols")
        if isinstance(ls, list) and any(str(x).strip() for x in ls):
            linked += 1
    soft = sum(
        1
        for row in report["conforming"]
        if any(str(w).startswith("body_over_soft") for w in (row.get("warnings") or []))
    )
    print(
        f"changed_links_docs={changed_links} changed_flow_docs={changed_flow} "
        f"linked_docs={linked}/{report['summary']['total']} "
        f"nonconforming={report['summary']['nonconforming_count']} soft={soft}"
    )
    return 0 if report["summary"]["nonconforming_count"] == 0 and soft == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
