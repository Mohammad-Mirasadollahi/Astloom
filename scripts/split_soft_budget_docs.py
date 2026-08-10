#!/usr/bin/env python3
"""Split docs that exceed the soft body-line budget into sibling Markdown files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "backend" / "packages"),
    str(ROOT / "backend" / "services" / "code-graph-service" / "src"),
]

from astloom_cli.commands.docs_standards.check import SOFT_BODY_LINES, check_markdown_doc
from astloom_cli.commands.docs_standards.collect import build_docs_standards_report
from astloom_cli.commands.docs_standards.remediate import remediate_markdown_doc
from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter

H2_RE = re.compile(r"(?m)^(##\s+.+)$")
TARGET = SOFT_BODY_LINES - 20  # leave headroom after split


def _sections(body: str) -> list[tuple[str, str]]:
    """Return [(heading_or_empty, section_text including heading)]."""
    matches = list(H2_RE.finditer(body))
    if not matches:
        return [("", body)]
    parts: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        parts.append(("", body[: matches[0].start()]))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chunk = body[match.start() : end]
        parts.append((match.group(1).strip(), chunk))
    return parts


def _split_one(path: Path, repo: Path) -> Path | None:
    rel = str(path.relative_to(repo)).replace("\\", "/")
    text = path.read_text(encoding="utf-8")
    fm, body = parse_markdown_frontmatter(text)
    if len(body.splitlines()) <= SOFT_BODY_LINES:
        return None

    sections = _sections(body)
    head_parts: list[str] = []
    tail_parts: list[str] = []
    used = 0
    for heading, chunk in sections:
        lines = len(chunk.splitlines())
        # Always keep preamble + Purpose in the head when possible.
        keep_in_head = (
            not heading
            or heading.lower().startswith("## purpose")
            or (used + lines <= TARGET and not tail_parts)
        )
        if keep_in_head and not tail_parts:
            head_parts.append(chunk)
            used += lines
        else:
            tail_parts.append(chunk)

    if not tail_parts or not head_parts:
        return None

    stem = path.stem
    # Avoid colliding with existing numbers: use -continued suffix.
    cont_name = f"{stem}-continued.md"
    cont_path = path.with_name(cont_name)
    n = 2
    while cont_path.exists():
        cont_name = f"{stem}-continued-{n}.md"
        cont_path = path.with_name(cont_name)
        n += 1

    cont_rel = str(cont_path.relative_to(repo)).replace("\\", "/")
    title = str((fm or {}).get("title") or stem)
    cont_title = f"{title} (Continued)"

    head_body = "".join(head_parts).rstrip() + (
        f"\n\n## Related Documents\n\n"
        f"- Continued in `{cont_rel}`\n"
    )
    # Avoid duplicate Related Documents heading if already present near end.
    if re.search(r"(?im)^##\s+related documents\s*$", "".join(head_parts)):
        head_body = "".join(head_parts).rstrip() + f"\n\n- Continued in `{cont_rel}`\n"

    tail_body = (
        f"# {cont_title}\n\n"
        f"## Purpose\n\n"
        f"Continuation of `{rel}` — remaining sections after the soft size budget.\n\n"
        + "".join(tail_parts).lstrip()
        + f"\n\n## Related Documents\n\n- Parent document: `{rel}`\n"
    )

    head_text = remediate_markdown_doc(
        relative_path=rel,
        text=f"---\nplaceholder: 1\n---\n\n# {title}\n\n{head_body}",
        repo=repo,
    )
    # Preserve identity fields from original where possible.
    old_fm, _ = parse_markdown_frontmatter(text)
    new_fm, new_body = parse_markdown_frontmatter(head_text)
    if old_fm:
        for key in ("doc_id", "owner", "status", "doc_type", "phase", "tags", "linked_symbols"):
            if key in old_fm and old_fm[key] not in (None, "", []):
                new_fm[key] = old_fm[key]
        new_fm["title"] = title
        new_fm["canonical_path"] = rel
        new_fm["summary"] = str(old_fm.get("summary") or new_fm.get("summary") or title)
    from astloom_cli.commands.docs_standards.remediate import _dump_frontmatter

    head_out = f"---\n{_dump_frontmatter(new_fm)}---\n\n{new_body.lstrip()}"
    cont_out = remediate_markdown_doc(
        relative_path=cont_rel,
        text=tail_body,
        repo=repo,
    )

    # Ensure both pass soft budget (or at least hard); recurse if needed later.
    path.write_text(head_out, encoding="utf-8")
    cont_path.write_text(cont_out, encoding="utf-8")
    return cont_path


def main() -> int:
    report = build_docs_standards_report(repo=ROOT)
    soft_files = [
        row["file"]
        for row in report["conforming"]
        if any(str(w).startswith("body_over_soft_budget") for w in (row.get("warnings") or []))
    ]
    created: list[str] = []
    for rel in soft_files:
        path = ROOT / rel
        if not path.is_file():
            continue
        # May need multiple passes if still soft after one split.
        for _ in range(4):
            text = path.read_text(encoding="utf-8")
            row = check_markdown_doc(relative_path=rel, text=text)
            soft = any(str(w).startswith("body_over_soft_budget") for w in (row.get("warnings") or []))
            hard = any(str(i).startswith("body_over_hard_budget") for i in (row.get("issues") or []))
            if not soft and not hard:
                break
            cont = _split_one(path, ROOT)
            if cont is None:
                break
            created.append(str(cont.relative_to(ROOT)))
            # Re-check/remediate head after write
            path.write_text(
                remediate_markdown_doc(
                    relative_path=rel,
                    text=path.read_text(encoding="utf-8"),
                    repo=ROOT,
                ),
                encoding="utf-8",
            )

    final = build_docs_standards_report(repo=ROOT)
    soft_left = [
        row["file"]
        for row in final["conforming"]
        if any(str(w).startswith("body_over_soft_budget") for w in (row.get("warnings") or []))
    ]
    out = ROOT / ".astloom" / "docs-soft-split-result.txt"
    lines = [
        f"created={len(created)}",
        f"conforming={final['summary']['conforming_count']}/{final['summary']['total']}",
        f"nonconforming={final['summary']['nonconforming_count']}",
        f"soft_left={len(soft_left)}",
        *[f"NEW {c}" for c in created],
        *[f"SOFT {s}" for s in soft_left],
        *[
            f"FAIL {row['file']} :: {', '.join(row.get('issues') or [])}"
            for row in final["nonconforming"][:30]
        ],
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    return 0 if final["summary"]["nonconforming_count"] == 0 and not soft_left else 1


if __name__ == "__main__":
    raise SystemExit(main())
