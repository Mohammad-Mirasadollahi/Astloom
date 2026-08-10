"""GAP-006 WeightProfile governance."""

from __future__ import annotations

import pytest

from weight_profiles import (
    WeightProfileError,
    activate_profile,
    get_active_profile_id,
    list_profiles,
    load_profile,
    rollback_profile,
    validate_profile,
)


def test_catalog_lists_defaults():
    ids = list_profiles()
    assert "default-memory-profile" in ids
    assert "conservative-memory-profile" in ids


def test_load_and_validate_default():
    profile = load_profile("default-memory-profile")
    assert profile["owner"] == "memory-platform"
    assert validate_profile(profile) == []


def test_validate_rejects_missing_weights():
    with pytest.raises(WeightProfileError):
        validate_profile({"profile_id": "x", "version": 1, "owner": "o", "status": "active"})


def test_activate_and_rollback(tmp_path):
    first = activate_profile(
        tmp_path,
        "conservative-memory-profile",
        actor="lead",
        reason="tighten",
        now_iso="2026-07-23T00:00:00Z",
    )
    assert first["active_profile_id"] == "conservative-memory-profile"
    assert get_active_profile_id(tmp_path) == "conservative-memory-profile"
    rolled = rollback_profile(
        tmp_path,
        actor="lead",
        reason="undo",
        now_iso="2026-07-23T00:01:00Z",
        steps=1,
    )
    assert rolled["active_profile_id"] == "default-memory-profile"


def test_activate_same_profile_is_idempotent_and_rollback_still_works(tmp_path):
    activate_profile(
        tmp_path,
        "conservative-memory-profile",
        actor="lead",
        reason="tighten",
        now_iso="2026-07-23T00:00:00Z",
    )
    again = activate_profile(
        tmp_path,
        "conservative-memory-profile",
        actor="lead",
        reason="again",
        now_iso="2026-07-23T00:00:30Z",
    )
    assert again.get("unchanged") is True
    rolled = rollback_profile(
        tmp_path,
        actor="lead",
        reason="undo",
        now_iso="2026-07-23T00:01:00Z",
        steps=1,
    )
    assert rolled["active_profile_id"] == "default-memory-profile"


def test_activate_denied_by_admin_matrix(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_ENFORCE_ADMIN_MATRIX", "1")
    with pytest.raises(WeightProfileError, match="denied by admin permission matrix"):
        activate_profile(
            tmp_path,
            "conservative-memory-profile",
            actor="viewer",
            reason="nope",
            now_iso="2026-07-23T00:00:00Z",
            roles=["viewer"],
        )


def test_activate_fail_closed_when_governance_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_ENFORCE_ADMIN_MATRIX", "1")
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "architecture_governance" or name.startswith("architecture_governance."):
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    with pytest.raises(WeightProfileError, match="requires architecture_governance"):
        activate_profile(
            tmp_path,
            "conservative-memory-profile",
            actor="admin",
            reason="enforce",
            now_iso="2026-07-23T00:00:00Z",
            roles=["admin"],
        )
