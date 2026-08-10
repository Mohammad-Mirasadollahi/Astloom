#!/usr/bin/env python3
"""Apply docs-standards remediation across docs/ and print a summary."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "backend" / "packages"),
    str(ROOT / "backend" / "services" / "code-graph-service" / "src"),
]

from astloom_cli.commands.docs_standards.collect import build_docs_standards_report
from astloom_cli.commands.docs_standards.remediate import remediate_tree


def main() -> int:
    docs = ROOT / "docs"
    force = "--force" in sys.argv
    result = remediate_tree(docs, repo=ROOT, force=force)
    report = build_docs_standards_report(repo=ROOT)
    summary = report["summary"]
    out = ROOT / ".astloom" / "docs-remediate-result.txt"
    lines = [
        f"changed={result['changed']}",
        f"still_failing={len(result['still_failing'])}",
        f"conforming={summary['conforming_count']}/{summary['total']} ({summary['percent_conforming']}%)",
        f"nonconforming={summary['nonconforming_count']}/{summary['total']} ({summary['percent_nonconforming']}%)",
    ]
    for row in result["still_failing"][:50]:
        lines.append(f"FAIL {row['file']} :: {', '.join(row['issues'])}")
    for row in report["nonconforming"][:50]:
        lines.append(f"OPEN {row['file']} :: {', '.join(row.get('issues') or [])}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    return 0 if summary["nonconforming_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
