from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import httpx
import pytest

from change_society.domain.models import DependencyError, ValidationError
from change_society.infrastructure.alibaba_ecs import AlibabaCloudEcsProof, AlibabaEcsTarget
from change_society.infrastructure.evidence_catalog import DEMO_SCENARIO_IDS
from change_society.interfaces.api import create_api

from conftest import HEADERS, make_service


def test_alibaba_ecs_requires_region_and_instance():
    proof = AlibabaCloudEcsProof(cli_binary="aliyun")
    with pytest.raises(ValidationError):
        proof.describe_instance(AlibabaEcsTarget("", "i-1"))


def test_alibaba_ecs_cli_missing():
    proof = AlibabaCloudEcsProof(cli_binary="/no/such/aliyun-binary")
    with pytest.raises(DependencyError) as exc:
        proof.describe_instance(AlibabaEcsTarget("cn-hangzhou", "i-1"))
    assert exc.value.code == "alibaba_cli_missing"


def test_alibaba_ecs_invalid_json_stdout(monkeypatch):
    proof = AlibabaCloudEcsProof(cli_binary="aliyun")

    def fake_run(command, check, capture_output, text):
        return MagicMock(stdout="not-json", returncode=0)

    monkeypatch.setattr("change_society.infrastructure.alibaba_ecs.subprocess.run", fake_run)
    with pytest.raises(DependencyError) as exc:
        proof.describe_instance(AlibabaEcsTarget("cn-hangzhou", "i-1"))
    assert exc.value.code == "alibaba_ecs_invalid_response"


def test_judging_engineering_profile_endpoint():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/hackathon/judging-engineering-profile")
            assert response.status_code == 200
            criteria = response.json()["profile"]["criteria"]
            assert len(criteria) == 4
            assert sum(item["weight_percent"] for item in criteria) == 100

    asyncio.run(exercise())


def test_health_liveness_always_ok():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    asyncio.run(exercise())


def test_list_demo_scenarios_and_conflicts():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            scenarios = await client.get("/api/v1/projects/project-a/demo-scenarios", headers=HEADERS)
            assert scenarios.status_code == 200
            items = scenarios.json()["items"]
            assert len(items) == len(DEMO_SCENARIO_IDS)
            for item in items:
                assert len(item.get("judge_demo_request", "")) >= 10

            created = await client.post(
                "/api/v1/projects/project-a/society-runs",
                headers={**HEADERS, "Idempotency-Key": "conflict-list"},
                json={"scenario_id": "pricing-refactor"},
            )
            run_id = created.json()["society_run"]["run_id"]
            conflicts = await client.get(
                f"/api/v1/projects/project-a/society-runs/{run_id}/conflicts",
                headers=HEADERS,
            )
            assert conflicts.status_code == 200
            assert len(conflicts.json()["items"]) >= 1

    asyncio.run(exercise())


def test_evaluate_baseline_endpoint():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v1/projects/project-a/society-runs",
                headers={**HEADERS, "Idempotency-Key": "eval-base"},
                json={"scenario_id": "pricing-refactor"},
            )
            run_id = created.json()["society_run"]["run_id"]
            evaluation = await client.post(
                f"/api/v1/projects/project-a/society-runs/{run_id}:evaluate-baseline",
                headers=HEADERS,
            )
            assert evaluation.status_code == 200
            body = evaluation.json()["evaluation"]
            assert "tradeoffs" in body
            assert "baseline" in body and "society" in body

    asyncio.run(exercise())


def test_reject_society_run():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v1/projects/project-a/society-runs",
                headers={**HEADERS, "Idempotency-Key": "reject-run"},
                json={"scenario_id": "pricing-refactor"},
            )
            run = created.json()["society_run"]
            rejected = await client.post(
                f"/api/v1/projects/project-a/society-runs/{run['run_id']}:reject",
                headers={**HEADERS, "Idempotency-Key": "reject-decision"},
                json={"reason": "Insufficient evidence.", "expected_version": run["version"]},
            )
            assert rejected.status_code == 200
            assert rejected.json()["society_run"]["state"] == "rejected"

    asyncio.run(exercise())


def test_submission_compliance_endpoint():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/hackathon/submission-compliance")
            assert response.status_code == 200
            body = response.json()["report"]
            assert body["track"].startswith("Track 3")
            assert "judging_engineering_profile" in body

    asyncio.run(exercise())


def test_evaluate_all_scenarios_endpoint():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/projects/project-a/society-runs:evaluate-all-scenarios",
                headers={**HEADERS, "Idempotency-Key": "eval-all"},
            )
            assert response.status_code == 200
            payload = response.json()
            evaluation = payload["evaluation"]
            assert evaluation["sample_count"] == len(DEMO_SCENARIO_IDS)
            assert len(evaluation["scenarios"]) == len(DEMO_SCENARIO_IDS)

    asyncio.run(exercise())


def test_get_agent_ticket_by_id():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v1/projects/project-a/society-runs",
                headers={**HEADERS, "Idempotency-Key": "ticket-get"},
                json={"scenario_id": "pricing-refactor"},
            )
            run_id = created.json()["society_run"]["run_id"]
            tickets = await client.get(f"/api/v1/projects/project-a/agent-tickets?run_id={run_id}", headers=HEADERS)
            ticket_id = tickets.json()["items"][0]["ticket_id"]
            one = await client.get(f"/api/v1/projects/project-a/agent-tickets/{ticket_id}", headers=HEADERS)
            assert one.status_code == 200
            assert one.json()["ticket"]["ticket_id"] == ticket_id

    asyncio.run(exercise())
