"""Schema registry catalog checks (GAP-008)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CATALOG = ROOT / "backend" / "tools" / "schema-registry" / "catalog.json"


def test_catalog_lists_existing_schemas() -> None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert data["shape"] == "repository_directory"
    assert data["schemas"], "catalog must list at least one schema"
    ids: set[str] = set()
    for entry in data["schemas"]:
        schema_id = entry["schema_id"]
        assert schema_id not in ids
        ids.add(schema_id)
        path = ROOT / entry["path"]
        assert path.is_file(), entry["path"]
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(schema, dict)
        assert schema.get("title") or schema.get("$id")
    assert "model-routing-profile" in ids
    assert "domain-pack" in ids
