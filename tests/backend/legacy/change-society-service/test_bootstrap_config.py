from __future__ import annotations

import pytest

from change_society.bootstrap.config import Settings


def test_settings_default_to_langgraph_integrator_profile(monkeypatch):
    monkeypatch.delenv("CHANGE_SOCIETY_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("CHANGE_SOCIETY_STORE", raising=False)
    monkeypatch.delenv("CHANGE_SOCIETY_WEBHOOK_AGENT_SECRET", raising=False)
    settings = Settings.load()
    assert settings.model_provider == "fake"
    assert settings.store == "memory"
    assert settings.webhook_agent_secret == "integrator-demo-secret-change-me"


def test_settings_reject_production_without_qwen_and_postgresql(monkeypatch):
    monkeypatch.setenv("CHANGE_SOCIETY_ENVIRONMENT", "production")
    monkeypatch.setenv("CHANGE_SOCIETY_MODEL_PROVIDER", "fake")
    with pytest.raises(ValueError, match="production requires"):
        Settings.load()


def test_settings_require_qwen_key_when_provider_is_qwen(monkeypatch):
    monkeypatch.setenv("CHANGE_SOCIETY_MODEL_PROVIDER", "qwen")
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("QWEN_API_KEY", "")
    with pytest.raises(ValueError, match="QWEN_API_KEY"):
        Settings.load()


def test_settings_require_database_url_for_postgresql_store(monkeypatch):
    monkeypatch.setenv("CHANGE_SOCIETY_STORE", "postgresql")
    monkeypatch.delenv("CHANGE_SOCIETY_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings.load()
