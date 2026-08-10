from __future__ import annotations

from datetime import UTC, datetime

from shared_kernel import (
    AppError,
    Err,
    FakeClock,
    Ok,
    is_err,
    is_ok,
    load_environment_profile,
    load_technology_profile,
    require_fields,
    validate_environment_profile,
    validate_technology_profile,
)


def test_technology_profile_loads_and_validates():
    profile = load_technology_profile()
    assert profile["profile_id"] == "default"
    assert validate_technology_profile(profile) == []


def test_environment_profiles_load_and_validate():
    for name in ("local", "dev", "test", "stage", "prod"):
        profile = load_environment_profile(name)
        assert validate_environment_profile(profile, expected_name=name) == []


def test_result_and_error_primitives():
    assert is_ok(Ok(1))
    assert is_err(Err("x"))
    public = AppError("task_not_found", "not_found_error", "missing", correlation_id="c1").to_public()
    assert public["error"]["category"] == "not_found_error"


def test_fake_clock_and_validation():
    clock = FakeClock(datetime(2026, 7, 18, tzinfo=UTC))
    assert clock.now().year == 2026
    assert require_fields({"a": 1}, ("a", "b")) == ["missing field: b"]
