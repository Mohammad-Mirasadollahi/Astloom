#!/usr/bin/env python3
"""Finish soft-budget cleanup for the CLI command-reference chain."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path("/opt/Astloom")
sys.path[:0] = [
    str(ROOT / "backend" / "packages"),
    str(ROOT / "backend" / "services" / "code-graph-service" / "src"),
]

from astloom_cli.commands.docs_standards.check import check_markdown_doc
from astloom_cli.commands.docs_standards.collect import build_docs_standards_report
from astloom_cli.commands.docs_standards.remediate import _dump_frontmatter, remediate_markdown_doc
from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter


def collapse_related(body: str) -> str:
    parts = re.split(r"(?m)^## Related Documents\s*$", body)
    if len(parts) <= 2:
        return body
    bullets: list[str] = []
    seen: set[str] = set()
    for part in parts[1:]:
        for bullet in re.findall(r"(?m)^- .+$", part):
            if bullet not in seen:
                seen.add(bullet)
                bullets.append(bullet)
    return parts[0].rstrip() + "\n\n## Related Documents\n\n" + "\n".join(bullets) + "\n"


def main() -> int:
    rel = (
        "docs/08-software-engineering-architecture/"
        "42-astloom-cli-command-reference-continued-continued-continued.md"
    )
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    fm, body = parse_markdown_frontmatter(text)
    body2 = collapse_related(body)
    h3 = list(re.finditer(r"(?m)^(###\s+.+)$", body2))
    mid = max(3, len(h3) // 2)
    cut = h3[mid].start()
    head = re.sub(r"\n## Related Documents[\s\S]*$", "", body2[:cut]).rstrip()
    tail = re.sub(r"\n## Related Documents[\s\S]*$", "", body2[cut:]).rstrip()

    cont_rel = (
        "docs/08-software-engineering-architecture/"
        "42-astloom-cli-command-reference-part-4.md"
    )
    title = str(fm.get("title") or "Command reference")
    head_body = (
        head
        + f"\n\n## Related Documents\n\n- Continued command catalog: `{cont_rel}`\n"
    )
    if not re.search(r"(?m)^#\s+", head_body):
        head_body = f"# {title}\n\n" + head_body
    tail_body = (
        f"# {title} (Part 4)\n\n"
        "## Purpose\n\n"
        f"Remaining `astloom` command catalog entries split from `{rel}` "
        "to satisfy the soft body-size budget.\n\n"
        "## Command catalog (continued)\n\n"
        + tail
        + f"\n\n## Related Documents\n\n- Previous chunk: `{rel}`\n"
    )

    head_out = remediate_markdown_doc(
        relative_path=rel,
        text="---\nx: 1\n---\n\n" + head_body,
        repo=ROOT,
    )
    new_fm, new_body = parse_markdown_frontmatter(head_out)
    for key in ("doc_id", "owner", "status", "doc_type", "phase", "tags", "linked_symbols", "summary"):
        if fm.get(key) not in (None, "", []):
            new_fm[key] = fm[key]
    new_fm["title"] = title
    new_fm["canonical_path"] = rel
    head_final = f"---\n{_dump_frontmatter(new_fm)}---\n\n{new_body.lstrip()}"
    cont_final = remediate_markdown_doc(relative_path=cont_rel, text=tail_body, repo=ROOT)
    path.write_text(head_final, encoding="utf-8")
    (ROOT / cont_rel).write_text(cont_final, encoding="utf-8")

    for p in (ROOT / "docs").rglob("*.md"):
        raw = p.read_text(encoding="utf-8")
        doc_fm, doc_body = parse_markdown_frontmatter(raw)
        collapsed = collapse_related(doc_body)
        if collapsed != doc_body:
            rel_p = str(p.relative_to(ROOT)).replace("\\", "/")
            fixed = remediate_markdown_doc(
                relative_path=rel_p,
                text=f"---\n{_dump_frontmatter(doc_fm)}---\n\n{collapsed.lstrip()}",
                repo=ROOT,
            )
            p.write_text(fixed, encoding="utf-8")

    report = build_docs_standards_report(repo=ROOT)
    soft = [
        row["file"]
        for row in report["conforming"]
        if any(str(w).startswith("body_over_soft_budget") for w in (row.get("warnings") or []))
    ]
    print(
        f"conforming={report['summary']['conforming_count']}/"
        f"{report['summary']['total']} non={report['summary']['nonconforming_count']} soft={len(soft)}"
    )
    for item in soft:
        print("SOFT", item)
        row = check_markdown_doc(
            relative_path=item,
            text=(ROOT / item).read_text(encoding="utf-8"),
        )
        print(" ", row.get("warnings"))
    return 0 if report["summary"]["nonconforming_count"] == 0 and not soft else 1


if __name__ == "__main__":
    raise SystemExit(main())
