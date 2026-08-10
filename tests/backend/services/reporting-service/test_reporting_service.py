import asyncio

from httpx import ASGITransport, AsyncClient

from reporting_service.api import app
from reporting_service.core import ReportingService
from reporting_service.testing import InMemoryStore


H = {"X-Tenant-Id": "t", "X-Workspace-Id": "w", "X-Actor-Id": "reporter", "Idempotency-Key": "one"}


class ApiClient:
    def __init__(self, api):
        self.api = api

    def request(self, method: str, url: str, **kwargs):
        async def execute():
            async with AsyncClient(transport=ASGITransport(app=self.api), base_url="http://test") as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(execute())

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)


def test_record_samples_and_compare():
    store = InMemoryStore()
    client = ApiClient(app(ReportingService(store)))
    with_sample = client.post(
        "/api/v1/projects/p/kpi-samples",
        headers=H,
        json={"kpi_name": "bug_reduction", "cohort": "with_astloom", "value": 12},
    )
    assert with_sample.status_code == 200
    client.post(
        "/api/v1/projects/p/kpi-samples",
        headers={**H, "Idempotency-Key": "two"},
        json={"kpi_name": "bug_reduction", "cohort": "without_astloom", "value": 4},
    )
    report = client.get("/api/v1/projects/p/kpi-compare", headers=H, params={"kpi_name": "bug_reduction"})
    assert report.json()["report"]["comparison_method"] == "with-or-without-astloom"
    assert report.json()["report"]["delta"] == 8.0
    assert store.outbox()[0]["event_type"] == "kpi.sample_recorded"


def test_compare_requires_both_cohorts():
    client = ApiClient(app(ReportingService(InMemoryStore())))
    client.post(
        "/api/v1/projects/p/kpi-samples",
        headers=H,
        json={"kpi_name": "token_consumption", "cohort": "with_astloom", "value": 1},
    )
    bad = client.get("/api/v1/projects/p/kpi-compare", headers=H, params={"kpi_name": "token_consumption"})
    assert bad.status_code == 400


def test_invalid_cohort_rejected():
    client = ApiClient(app(ReportingService(InMemoryStore())))
    bad = client.post(
        "/api/v1/projects/p/kpi-samples",
        headers=H,
        json={"kpi_name": "x", "cohort": "maybe", "value": 1},
    )
    assert bad.status_code == 400


def test_benefit_summary_token_and_quality(tmp_path):
    from reporting_service.core import Scope
    from reporting_service.testing import DictStore

    path = tmp_path / "reporting.json"
    store = DictStore(str(path))
    client = ApiClient(app(ReportingService(store)))
    samples = [
        ("a", "token_consumption", "with_astloom", 10),
        ("b", "token_consumption", "without_astloom", 40),
        ("c", "quality_score", "with_astloom", 0.9),
        ("d", "quality_score", "without_astloom", 0.5),
    ]
    for key, kpi, cohort, value in samples:
        client.post(
            "/api/v1/projects/p/kpi-samples",
            headers={**H, "Idempotency-Key": key},
            json={"kpi_name": kpi, "cohort": cohort, "value": value},
        )
    summary = client.get("/api/v1/projects/p/kpi-benefit-summary", headers=H)
    body = summary.json()["summary"]
    assert body["kpi_count"] == 2
    assert body["token_savings_delta"] == 30.0
    assert body["quality_delta"] == 0.4
    reloaded = DictStore(str(path))
    assert len(reloaded.list_samples(Scope("t", "w", "p"))) == 4
