"""GAP-T04 prompt-context verification: ContextBundle audit + safety tests."""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import jsonschema
import pytest

from memory_service.core import MemoryService, Scope, estimate_tokens
from memory_service.domain.bundle_verifier import (
    OMITTED_HIGH_SCORER,
    REF_MALFORMED,
    RESTRICTED_INCLUDED,
    STALE_AFTER_BUILD,
    validate_bundle_schema,
    verify_context_bundle,
)
from memory_service.testing import InMemoryStore

SCOPE = Scope("t", "w", "p")
SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "backend"
    / "configs"
    / "schemas"
    / "context-bundle-audit.schema.json"
)


def memory(kind="semantic", title="Current architecture rule", body="Use dependency injection for memory retrieval.", **extra):
    return {
        "kind": kind,
        "title": title,
        "body": body,
        "tags": extra.pop("tags", ["architecture", "memory"]),
        "evidence_refs": extra.pop("evidence_refs", ["decision-1"]),
        "source_refs": extra.pop("source_refs", ["worklog-1"]),
        "confidence": extra.pop("confidence", 0.9),
        **extra,
    }


def test_verify_fresh_bundle_passes_schema_and_checks():
    store = InMemoryStore()
    service = MemoryService(store)
    created = service.create_memory(SCOPE, "agent", "corr", "one", memory())
    service.consolidate_memory(SCOPE, "agent", "corr", "c1", [created.id], "activate")
    bundle = service.retrieve_context(
        SCOPE, "agent", "corr", "memory dependency injection architecture", token_budget=200
    )
    result = verify_context_bundle(
        bundle,
        expected_scope=SCOPE,
        candidates=store.list_memory(SCOPE),
        profile=service.profile,
        schema_path=SCHEMA_PATH,
    )
    assert result.ok, result.public()
    assert not validate_bundle_schema(bundle.public(), schema_path=SCHEMA_PATH)


def test_stale_after_build_detected():
    store = InMemoryStore()
    service = MemoryService(store)
    created = service.create_memory(SCOPE, "agent", "corr", "one", memory())
    service.consolidate_memory(SCOPE, "agent", "corr", "c1", [created.id], "activate")
    bundle = service.retrieve_context(
        SCOPE, "agent", "corr", "memory dependency injection architecture", token_budget=200
    )
    # Mutate live candidate after build (version + body).
    live = store.get_memory(created.id, SCOPE)
    live.body = "Use dependency injection for memory retrieval — revised."
    live.version += 1
    live.updated_at = "2099-01-01T00:00:00+00:00"
    store.put_memory(live)

    result = verify_context_bundle(
        bundle,
        expected_scope=SCOPE,
        candidates=store.list_memory(SCOPE),
        profile=service.profile,
        schema_path=SCHEMA_PATH,
    )
    assert not result.ok
    assert any(f.code == STALE_AFTER_BUILD for f in result.findings)
    from architecture_governance import read_model

    catalog = read_model("memory.context_bundle")
    assert catalog["invalidation"] == "source_memory_version_change"
    assert catalog["build"] == "on_demand"


def test_omitted_high_scorer_fails():
    store = InMemoryStore()
    service = MemoryService(store)
    created = service.create_memory(SCOPE, "agent", "corr", "one", memory())
    service.consolidate_memory(SCOPE, "agent", "corr", "c1", [created.id], "activate")
    bundle = service.retrieve_context(
        SCOPE, "agent", "corr", "memory dependency injection architecture", token_budget=200
    )
    payload = bundle.public()
    # Drop the included item entirely and leave excluded empty → high scorer omitted.
    payload["items"] = []
    payload["excluded"] = []
    candidates = [
        {
            **created.public(),
            "score": 99.0,
        }
    ]
    result = verify_context_bundle(
        payload,
        expected_scope=SCOPE,
        candidates=candidates,
        profile=service.profile,
        schema_path=SCHEMA_PATH,
    )
    assert not result.ok
    assert any(f.code == OMITTED_HIGH_SCORER for f in result.findings)


def test_restricted_never_in_items_and_redaction():
    store = InMemoryStore()
    service = MemoryService(store)
    restricted = service.create_memory(
        SCOPE,
        "agent",
        "corr",
        "restricted",
        memory("restricted", "Secret token rule", "api_key=supersecret must never enter prompts."),
    )
    assert "supersecret" not in restricted.body
    assert "[REDACTED]" in restricted.body

    bundle = service.retrieve_context(
        SCOPE, "agent", "corr", "secret token rule prompts", token_budget=200
    ).public()
    assert restricted.id not in [item["memory"]["id"] for item in bundle["items"]]
    assert any(e["id"] == restricted.id and e["reason"] == "restricted_memory_boundary" for e in bundle["excluded"])

    # Tamper: force restricted into items → verifier fails.
    tampered = copy.deepcopy(bundle)
    tampered["items"] = [
        {
            "memory": restricted.public(),
            "score": 9.0,
            "selection_reason": "tampered",
            "token_estimate": estimate_tokens(restricted.title + " " + restricted.body),
        }
    ]
    tampered["excluded"] = [e for e in tampered["excluded"] if e["id"] != restricted.id]
    result = verify_context_bundle(
        tampered,
        expected_scope=SCOPE,
        candidates=store.list_memory(SCOPE),
        profile=service.profile,
        schema_path=SCHEMA_PATH,
    )
    assert not result.ok
    assert any(f.code == RESTRICTED_INCLUDED for f in result.findings)


def test_malformed_refs_rejected():
    store = InMemoryStore()
    service = MemoryService(store)
    created = service.create_memory(SCOPE, "agent", "corr", "one", memory())
    service.consolidate_memory(SCOPE, "agent", "corr", "c1", [created.id], "activate")
    bundle = service.retrieve_context(
        SCOPE, "agent", "corr", "memory dependency injection architecture", token_budget=200
    ).public()
    bundle["items"][0]["memory"]["source_refs"] = ["ok", ""]
    bundle["items"][0]["memory"]["evidence_refs"] = ["decision-1"]
    result = verify_context_bundle(
        bundle,
        expected_scope=SCOPE,
        candidates=store.list_memory(SCOPE),
        profile=service.profile,
        validate_schema=False,
    )
    assert not result.ok
    assert any(f.code == REF_MALFORMED for f in result.findings)

    bundle["items"][0]["memory"]["source_refs"] = ["bad\x00ref"]
    result2 = verify_context_bundle(
        bundle,
        expected_scope=SCOPE,
        candidates=store.list_memory(SCOPE),
        profile=service.profile,
        validate_schema=False,
    )
    assert any(f.code == REF_MALFORMED for f in result2.findings)


def test_schema_rejects_missing_required_and_fuzz_invalid():
    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"bundle_id": "x"})

    rng = random.Random(20260724)
    for _ in range(20):
        junk = {
            "bundle_id": rng.choice(["", None, 1, "ok"]),
            "tenant_id": rng.choice(["t", "", 0]),
            "workspace_id": "w",
            "project_id": "p",
            "query": rng.choice(["", "q"]),
            "token_budget": rng.choice([0, -1, "x", 10]),
            "weight_profile": rng.choice([{}, {"profile_id": "p", "version": 1}]),
            "prompt_cache": {"profile_id": "p", "version": 1},
            "items": rng.choice([[], "nope", [{"memory": {}}]]),
            "excluded": [],
            "built_at": "now",
        }
        errors = list(validator.iter_errors(junk))
        # At least some generated junk must fail; empty-string / zero budget / bad items are invalid.
        if junk["token_budget"] != 10 or junk["query"] == "" or junk["bundle_id"] != "ok":
            assert errors
