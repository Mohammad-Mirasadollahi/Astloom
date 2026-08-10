"""Validate DomainPack / FeatureProfile / RuleSuggestion config schemas (GAP-009)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[3]
CONFIGS = ROOT / "backend" / "configs"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema_path: Path):
    schema = _load(schema_path)
    return jsonschema.Draft202012Validator(schema)


@pytest.mark.parametrize(
    ("schema_name", "instance_rel"),
    [
        ("domain-packs/domain-pack.schema.json", "domain-packs/default.json"),
        ("feature-profiles/feature-profile.schema.json", "feature-profiles/default.json"),
        (
            "rule-packs/rule-suggestion.schema.json",
            "rule-packs/rule-suggestion.example.json",
        ),
    ],
)
def test_first_party_configs_match_schemas(schema_name: str, instance_rel: str) -> None:
    schema_path = CONFIGS / schema_name
    instance_path = CONFIGS / instance_rel
    assert schema_path.is_file(), schema_path
    assert instance_path.is_file(), instance_path
    errors = sorted(
        _validator(schema_path).iter_errors(_load(instance_path)),
        key=lambda e: e.path,
    )
    assert not errors, [e.message for e in errors]


def test_feature_profile_rejects_unknown_state() -> None:
    validator = _validator(CONFIGS / "feature-profiles" / "feature-profile.schema.json")
    bad = {
        "profile_id": "bad",
        "version": "1.0.0",
        "title": "Bad",
        "features": {"memory_retrieval": "maybe"},
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(bad)


def test_rule_suggestion_requires_evidence() -> None:
    validator = _validator(CONFIGS / "rule-packs" / "rule-suggestion.schema.json")
    bad = {
        "suggestion_id": "sug:x",
        "title": "X",
        "proposed_rule": {"category": "memory", "statement": "Keep facts scoped"},
        "scope": {"kind": "project", "id": "p1"},
        "risk": "low",
        "confidence": 0.5,
        "evidence": [],
        "status": "draft",
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(bad)


def test_default_domain_pack_disables_auto_activate() -> None:
    pack = _load(CONFIGS / "domain-packs" / "default.json")
    assert pack["suggestions"]["auto_activate_low_risk_rules"] is False
