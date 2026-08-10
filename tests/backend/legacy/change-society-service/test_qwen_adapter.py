import json

import httpx

from change_society.contracts.messages import RoleOutput
from change_society.domain.models import DependencyError
from change_society.infrastructure.qwen_client import QwenCloudClient


PAYLOAD = {
    "summary": "Evidence-backed risk analysis", "risk_level": "high", "findings": ["base_price changes"],
    "impacts": ["customer price"], "policies": ["revenue-impacting-change"], "tasks": ["request approval"],
    "evidence_refs": ["ev_diff_price"], "assumptions": [], "unresolved_questions": [], "confidence": 0.9,
    "recommended_action": "Request Product and Finance approval.",
}


def test_qwen_openai_compatible_mapping_and_schema_validation():
    seen = {}

    def handler(request):
        seen["authorization"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "qwen-test", "choices": [{"message": {"content": json.dumps(PAYLOAD)}}], "usage": {"prompt_tokens": 10, "completion_tokens": 8}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = QwenCloudClient("secret-value", "https://qwen.example/v1", "qwen-test", 3, 500, 0.1, 0, client)
    result = adapter.complete("policy_guardian", "system", "user", RoleOutput)
    assert result.payload["risk_level"] == "high"
    assert result.input_tokens == 10 and result.output_tokens == 8
    assert seen["authorization"] == "Bearer secret-value"
    assert "JSON SCHEMA" in seen["body"]["messages"][0]["content"]


def test_qwen_invalid_payload_is_typed_and_safe():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "not-json"}}]})))
    adapter = QwenCloudClient("secret-value", "https://qwen.example/v1", "qwen-test", 3, 500, 0.1, 0, client)
    try:
        adapter.complete("policy_guardian", "system", "user", RoleOutput)
        raise AssertionError("expected typed dependency error")
    except DependencyError as exc:
        assert exc.code == "qwen_schema_invalid"
        assert "secret-value" not in exc.message
