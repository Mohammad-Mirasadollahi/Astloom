from __future__ import annotations

import json

import httpx

from change_society.contracts.messages import RoleOutput
from change_society.domain.models import DependencyError
from change_society.infrastructure.fake_model import DeterministicModelClient
from change_society.infrastructure.qwen_client import QwenCloudClient


PAYLOAD = {
    "summary": "Evidence-backed risk analysis", "risk_level": "high", "findings": [], "impacts": [], "policies": [],
    "tasks": [], "evidence_refs": ["ev_1"], "assumptions": [], "unresolved_questions": [],
    "confidence": 0.9, "recommended_action": "approve",
}


def test_qwen_maps_authentication_and_rate_limit_errors():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401, json={"error": "bad key"})))
    adapter = QwenCloudClient("secret", "https://qwen.example/v1", "qwen-test", 3, 500, 0.1, 0, client)
    try:
        adapter.complete("policy_guardian", "system", "user", RoleOutput)
        raise AssertionError("expected auth failure")
    except DependencyError as exc:
        assert exc.code == "qwen_authentication_failed"
        assert exc.retryable is False


def test_qwen_retries_transient_provider_errors():
    attempts = {"count": 0}

    def handler(request):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(200, json={"model": "qwen-test", "choices": [{"message": {"content": json.dumps(PAYLOAD)}}], "usage": {"prompt_tokens": 3, "completion_tokens": 2}})

    adapter = QwenCloudClient("secret", "https://qwen.example/v1", "qwen-test", 3, 500, 0.1, 1, httpx.Client(transport=httpx.MockTransport(handler)))
    result = adapter.complete("policy_guardian", "system", "user", RoleOutput)
    assert result.output_tokens == 2
    assert attempts["count"] == 2


def test_qwen_maps_quota_exhausted():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(402, json={"error": "quota"})))
    adapter = QwenCloudClient("secret", "https://qwen.example/v1", "qwen-test", 3, 500, 0.1, 0, client)
    try:
        adapter.complete("policy_guardian", "system", "user", RoleOutput)
        raise AssertionError("expected quota failure")
    except DependencyError as exc:
        assert exc.code == "qwen_quota_exhausted"


def test_fake_model_branches_cover_baseline_and_rebuttal_paths():
    model = DeterministicModelClient()
    baseline = model.complete("single_agent_baseline", "s", "ev_diff_price", RoleOutput).payload
    assert baseline["impacts"] == ["customer price"]
    initial = model.complete("change_analyst", "s", "REQUEST ev_diff_price without rebuttal", RoleOutput).payload
    revised = model.complete("change_analyst", "s", "ONE BOUNDED REBUTTAL", RoleOutput).payload
    assert initial["risk_level"] == "low"
    assert revised["risk_level"] == "high"


def test_fake_model_health_marks_non_production_provider():
    assert DeterministicModelClient().health()["production_ready"] is False
