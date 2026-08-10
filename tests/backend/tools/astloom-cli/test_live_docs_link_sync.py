"""Live probe: astloom sync Phase-2 docs link on a real fixture tree."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
ASTLOOM = ROOT / ".venv" / "bin" / "astloom"


@pytest.mark.live
def test_live_astloom_sync_docs_link(tmp_path: Path) -> None:
    if not ASTLOOM.is_file():
        pytest.skip("astloom CLI not installed in .venv")

    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "auth.py").write_text(
        "def login(user, password):\n    return len(password) > 8\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "login.md").write_text(
        "\n".join(
            [
                "---",
                "doc_id: doc-live-login",
                "title: Live login doc",
                "owner: platform",
                "status: active",
                'schema_version: "1.0"',
                "linked_symbols:",
                "  - src.auth.login",
                "decision_refs: []",
                "---",
                "",
                "# Live login",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "astloom.sync.yaml").write_text(
        "\n".join(
            [
                "code:",
                "  exclude:",
                "    - '**/__pycache__/**'",
                "  include_extensions: [.py]",
                "docs:",
                "  match: ['**/*.md']",
                "  exclude: []",
                "",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["ASTLOOM_GRAPH_CLI_BACKEND"] = "memory"
    env["ASTLOOM_EMBEDDING_PROVIDER"] = "stub"
    env.pop("ASTLOOM_DOCS_SYNC_DATABASE_URL", None)

    proc = subprocess.run(
        [
            str(ASTLOOM),
            "sync",
            "--path",
            str(tmp_path),
            "--tenant",
            "live",
            "--workspace",
            "qa",
            "--project",
            "docs-link",
            "max-file",
            "50",
            "--progress-interval",
            "60",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    start = (proc.stdout or "").rfind("\n{")
    assert start >= 0, proc.stdout
    payload = json.loads(proc.stdout[start + 1 :])
    docs = payload.get("docs_link") or {}
    sync = payload.get("sync") or {}
    assert int(sync.get("files_ingested") or 0) >= 1
    assert int(docs.get("docs_indexed") or 0) >= 1
    assert int(docs.get("links_created") or 0) >= 1
    assert int(docs.get("anchors_registered") or 0) >= 1
    assert docs.get("unresolved_tokens") == []
