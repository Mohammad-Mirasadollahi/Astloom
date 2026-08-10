from __future__ import annotations

import asyncio

import httpx
from change_society.interfaces.api import create_api
from test_change_society import HEADERS, make_service


def test_readiness_reports_degraded_for_fake_dependencies():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/ready")
            assert response.status_code == 200
            body = response.json()
            assert body["status"] in {"degraded", "not_ready"}
            assert body["checks"]["model"]["provider"] == "deterministic_fake"

    asyncio.run(exercise())


def test_invalid_page_token_maps_to_validation_error():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/projects/project-a/demo-scenarios?page_token=not-a-number", headers=HEADERS)
            assert response.status_code == 400
            assert response.json()["error"]["category"] == "validation_error"

    asyncio.run(exercise())


def test_submission_compliance_endpoint_is_public():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service(), {"model_provider": "fake", "store": "memory", "environment": "development"}))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/hackathon/submission-compliance")
            assert response.status_code == 200
            report = response.json()["report"]
            assert report["track"].startswith("Track 3")

    asyncio.run(exercise())


def test_stale_approval_version_returns_conflict():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post("/api/v1/projects/project-a/society-runs", headers=HEADERS, json={"scenario_id": "pricing-refactor"})
            run = created.json()["society_run"]
            response = await client.post(
                f"/api/v1/projects/project-a/society-runs/{run['run_id']}:approve",
                headers={**HEADERS, "Idempotency-Key": "stale-approve"},
                json={"reason": "Too early", "expected_version": run["version"] + 10},
            )
            assert response.status_code == 409
            assert response.json()["error"]["category"] == "conflict_error"

    asyncio.run(exercise())
