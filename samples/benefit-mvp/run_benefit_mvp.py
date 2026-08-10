#!/usr/bin/env python3
"""Benefit MVP: with/without explore pack token proxy vs naive full-tree read.

Writes an end-to-end report under tests/artifacts/code-graph-eval/ (not KPI JSON alone).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = Path(__file__).resolve().parent.parent / "e2e-graph-probe" / "src"
OUT_DIR = ROOT / "tests" / "artifacts" / "code-graph-eval"

for p in (
    ROOT / "backend" / "packages",
    ROOT / "backend" / "services" / "code-graph-service" / "src",
):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore


def _chars_without_graph(root: Path) -> int:
    total = 0
    for path in root.rglob("*.py"):
        total += len(path.read_text(encoding="utf-8"))
    return total


def main() -> int:
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("benefit-t", "benefit-w", "benefit-p")
    ingest = svc.ingest_repo(
        scope,
        "benefit",
        "benefit-1",
        "benefit-repo",
        {
            "root_path": str(SAMPLE),
            "include_extensions": [".py"],
            "max_files": 20,
            "include_outcomes": True,
        },
    )
    ingest_dict = ingest.to_dict() if hasattr(ingest, "to_dict") else {}
    query = "how does login password verification work"
    pack = svc.explore(scope, query, top_k=12)
    with_chars = int(pack.get("used_chars") or 0)
    without_chars = _chars_without_graph(SAMPLE)
    saved = max(0, without_chars - with_chars)
    ratio = round(with_chars / without_chars, 4) if without_chars else 0.0
    report = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "query": query,
        "sample_root": str(SAMPLE),
        "ingest_files": ingest_dict.get("files_ingested"),
        "without_graph_chars": without_chars,
        "with_explore_chars": with_chars,
        "chars_saved_proxy": saved,
        "explore_over_naive_ratio": ratio,
        "notes": (
            "Proxy only: compares explore pack used_chars vs concatenating all .py sources. "
            "Not a production acceptance KPI; sales dry-run evidence for backlog 34 C3."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"benefit-mvp-{stamp}.json"
    latest = OUT_DIR / "benefit-mvp-latest.json"
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    md = OUT_DIR / "benefit-mvp-latest.md"
    md.write_text(
        "# Benefit MVP (with/without explore)\n\n"
        f"- Query: `{query}`\n"
        f"- Without graph (all `.py` chars): **{without_chars}**\n"
        f"- With explore pack (`used_chars`): **{with_chars}**\n"
        f"- Saved proxy: **{saved}** ({ratio:.0%} of naive size)\n"
        f"- Artifact: `{path.name}`\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "report": str(path), "chars_saved_proxy": saved}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
