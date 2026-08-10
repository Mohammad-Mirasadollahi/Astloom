"""Live smoke: Qwen free-tier compatible-mode API (operational, minimal cost)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SMOKE = ROOT / "archives" / "hackathon" / "scripts" / "smoke_qwen_free_api.py"


def _qwen_api_key_configured() -> bool:
    key = os.getenv("QWEN_API_KEY", "").strip()
    if key:
        return True
    env_path = ROOT / "archives" / "hackathon" / ".env"
    if not env_path.is_file():
        return False
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("QWEN_API_KEY="):
            return bool(line.split("=", 1)[1].strip())
    return False


pytestmark = pytest.mark.skipif(
    not _qwen_api_key_configured(),
    reason="QWEN_API_KEY required (non-empty hackathon/.env or env)",
)


def test_qwen_free_api_smoke_operational():
    """Runs the same script judges can use: raw chat + society RoleOutput."""
    completed = subprocess.run(
        [sys.executable, str(SMOKE)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "passed"
    evidence = ROOT / payload["evidence"]
    assert evidence.is_file()
    report = json.loads(evidence.read_text())
    assert report["steps"]["raw_chat_completion"]["ok"] is True
    assert report["steps"]["society_role_output"]["ok"] is True
    assert report["steps"]["society_role_output"]["risk_level"] in {"low", "medium", "high", "critical"}
