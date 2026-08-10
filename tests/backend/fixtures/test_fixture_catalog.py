"""GAP-T08: validate fixture catalog.json — paths, policy, no secrets, deterministic seed."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from synthetic_workflow import AUTH_PLACEHOLDER, generate_workflow

ROOT = Path(__file__).resolve().parents[3]
CATALOG = Path(__file__).resolve().parent / "catalog.json"

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|password|secret)\s*[:=]\s*(?!\[REDACTED\]|fixture-)(\S+)"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{16,}"),
    re.compile(r"(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def _load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def test_catalog_schema_and_policy():
    catalog = _load_catalog()
    assert catalog["schema_version"]
    policy = catalog["policy"]
    assert policy["no_secrets"] is True
    assert policy["no_customer_data"] is True
    assert "synthetic" in policy["classification_allowed"]
    assert catalog["fixtures"]


def test_catalog_fixture_paths_exist_and_no_secrets():
    catalog = _load_catalog()
    allowed_class = set(catalog["policy"]["classification_allowed"])
    allowed_families = set(catalog["policy"]["families_allowed"])
    for entry in catalog["fixtures"]:
        assert entry["id"]
        assert entry["classification"] in allowed_class
        assert set(entry["families"]) <= allowed_families
        path = ROOT / entry["path"]
        assert path.exists(), f"missing fixture path: {entry['path']}"
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in SECRET_PATTERNS:
                assert not pattern.search(text), f"secret-like content in {entry['path']}"
        else:
            for child in path.rglob("*"):
                if not child.is_file():
                    continue
                if child.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pyc"}:
                    continue
                text = child.read_text(encoding="utf-8", errors="replace")
                for pattern in SECRET_PATTERNS:
                    assert not pattern.search(text), f"secret-like content in {child}"


@pytest.mark.parametrize("seed", [0, 1, 42])
def test_synthetic_workflow_deterministic(seed: int):
    first = generate_workflow(seed)
    second = generate_workflow(seed)
    assert first.public() == second.public()
    assert first.auth_token == AUTH_PLACEHOLDER
    assert first.seed == seed
    # Distinct seeds must diverge (beyond seed=0 special case vs others).
    if seed != 0:
        other = generate_workflow(seed + 1)
        assert other.correlation_id != first.correlation_id
