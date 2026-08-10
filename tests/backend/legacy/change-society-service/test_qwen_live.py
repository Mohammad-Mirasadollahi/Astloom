import os

import pytest

from change_society.contracts.messages import RoleOutput
from change_society.infrastructure.qwen_client import QwenCloudClient

pytestmark = pytest.mark.skipif(not os.getenv("QWEN_API_KEY"), reason="QWEN_API_KEY is required for live provider evidence")


def test_live_qwen_structured_completion_is_schema_valid():
    client = QwenCloudClient(
        os.environ["QWEN_API_KEY"],
        os.getenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
        os.getenv("QWEN_MODEL", "qwen-plus"),
        float(os.getenv("QWEN_TIMEOUT_SECONDS", "30")),
        int(os.getenv("QWEN_MAX_OUTPUT_TOKENS", "800")),
        float(os.getenv("QWEN_TEMPERATURE", "0.1")),
        int(os.getenv("QWEN_MAX_RETRIES", "1")),
    )
    try:
        result = client.complete(
            "policy_guardian",
            "Return JSON only.",
            "Classify revenue risk for a checkout tax refactor that mutates base_price.",
            RoleOutput,
        )
        assert result.payload["risk_level"] in {"low", "medium", "high", "critical"}
        assert result.input_tokens > 0
        assert result.output_tokens > 0
    finally:
        client.close()
