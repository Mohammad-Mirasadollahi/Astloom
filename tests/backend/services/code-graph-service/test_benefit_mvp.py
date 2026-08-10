"""Benefit MVP report generation (backlog 34 C3)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_benefit_mvp_writes_report():
    script = ROOT / "samples" / "benefit-mvp" / "run_benefit_mvp.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    latest = ROOT / "tests" / "artifacts" / "code-graph-eval" / "benefit-mvp-latest.json"
    assert latest.is_file()
    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["without_graph_chars"] > 0
    assert "with_explore_chars" in payload
    assert (ROOT / "tests" / "artifacts" / "code-graph-eval" / "benefit-mvp-latest.md").is_file()
