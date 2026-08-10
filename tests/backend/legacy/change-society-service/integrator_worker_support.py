"""Import paths and constants for hackathon external worker integrator tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WORKER_SRC = ROOT / "archives" / "hackathon" / "examples" / "external-change-analyst-worker" / "src"
SDK_SRC = ROOT / "archives" / "hackathon" / "sdk" / "python"
INTEGRATOR_AGENTS_JSON = (
    ROOT / "archives" / "hackathon" / "backend" / "change-society-service" / "config" / "managed-agents.integrator.example.json"
)
DEFAULT_WEBHOOK_SECRET = "integrator-demo-secret-change-me"


def ensure_worker_import_path() -> Path:
    for directory in (WORKER_SRC, SDK_SRC, ROOT / "archives" / "hackathon" / "backend" / "change-society-service" / "src"):
        path = str(directory)
        if path not in sys.path:
            sys.path.insert(0, path)
    os.environ.setdefault("ASTLOOM_WEBHOOK_SHARED_SECRET", DEFAULT_WEBHOOK_SECRET)
    return ROOT


def load_integrator_registry() -> dict:
    return json.loads(INTEGRATOR_AGENTS_JSON.read_text(encoding="utf-8"))
