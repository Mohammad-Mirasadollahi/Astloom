from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from change_society.application.submission_compliance import build_submission_compliance_report
from change_society.infrastructure.alibaba_ecs import AlibabaCloudEcsProof, AlibabaEcsTarget
from change_society.infrastructure.fake_model import DeterministicModelClient
from change_society.infrastructure.repositories import InMemoryRunRepository


def test_submission_compliance_report_lists_track3_and_demo_gate():
    report = build_submission_compliance_report(
        model=DeterministicModelClient(),
        repository=InMemoryRunRepository(),
        model_provider="fake",
        store="memory",
        environment="development",
        alibaba_proof_module="change_society/infrastructure/alibaba_ecs.py",
        architecture_doc="archives/hackathon/docs/02-architecture.md",
        evaluation_artifact="archives/hackathon/evidence/real/evaluation-scenarios.json",
    )
    assert report["track"].startswith("Track 3")
    assert report["gates"]["local_demo_without_api_keys"] is True
    assert len(report["requirements"]) >= 7


def test_alibaba_ecs_proof_parses_cli_json(monkeypatch):
    proof = AlibabaCloudEcsProof(cli_binary="aliyun")
    payload = {"Instances": {"Instance": [{"InstanceId": "i-test"}]}}

    def fake_run(command, check, capture_output, text):
        assert "DescribeInstances" in command
        return MagicMock(stdout=json.dumps(payload), returncode=0)

    monkeypatch.setattr("change_society.infrastructure.alibaba_ecs.subprocess.run", fake_run)
    result = proof.describe_instance(AlibabaEcsTarget("cn-hangzhou", "i-test"))
    assert result["Instances"]["Instance"][0]["InstanceId"] == "i-test"
