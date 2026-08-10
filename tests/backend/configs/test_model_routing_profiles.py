"""Validate ModelRoutingProfile configs (GAP-003)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[3]
CONFIGS = ROOT / "backend" / "configs" / "model-routing"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["default.json", "cloud.json"])
def test_routing_profiles_match_schema(name: str) -> None:
    schema = _load(CONFIGS / "model-routing-profile.schema.json")
    instance = _load(CONFIGS / name)
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(instance),
        key=lambda e: list(e.path),
    )
    assert not errors, [e.message for e in errors]


def test_local_and_cloud_cover_required_task_risk_pairs() -> None:
    required = {
        (task, risk)
        for task in (
            "docs.generate",
            "rules.judge",
            "codegen.synthesize",
            "embed.symbol",
        )
        for risk in ("low", "medium", "high")
    }
    for name in ("default.json", "cloud.json"):
        routes = {
            (r["task_class"], r["risk_level"]) for r in _load(CONFIGS / name)["routes"]
        }
        assert required <= routes, name


def test_schema_rejects_unknown_task_class() -> None:
    schema = _load(CONFIGS / "model-routing-profile.schema.json")
    bad = {
        "profile_id": "bad",
        "version": "1.0.0",
        "title": "Bad",
        "environment": "local",
        "routes": [
            {
                "task_class": "unknown.task",
                "risk_level": "low",
                "primary_model": "x",
                "fallback_models": [],
                "json_mode": False,
                "allow_stub": True,
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(bad)
