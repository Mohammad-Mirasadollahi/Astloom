"""Write eval report JSON under tests/artifacts/code-graph-eval/."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def eval_artifact_root() -> Path:
    # tests/backend/services/code-graph-service/eval/reports.py → repo root parents[5]
    return Path(__file__).resolve().parents[5] / "tests" / "artifacts" / "code-graph-eval"


def write_eval_report(name: str, payload: dict[str, Any]) -> Path:
    root = eval_artifact_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = root / f"{name}-{stamp}.json"
    body = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "label_source": payload.get("label_source", "git_cochange_or_gold"),
        "circular_claim_ban": "ADR-19: labels must not come from graph self-walk",
        **payload,
    }
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest = root / f"{name}-latest.json"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return path
