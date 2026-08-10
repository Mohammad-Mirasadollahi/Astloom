from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


class ReportingError(Exception):
    def __init__(self, code: str, category: str, message: str):
        super().__init__(message)
        self.code, self.category, self.message = code, category, message


class ValidationError(ReportingError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class ConflictError(ReportingError):
    def __init__(self, message: str):
        super().__init__("conflict_error", "conflict_error", message)


class NotFoundError(ReportingError):
    def __init__(self, message: str):
        super().__init__("not_found", "not_found_error", message)


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    workspace_id: str
    project_id: str

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.workspace_id.strip(), self.project_id.strip())):
            raise ValidationError("tenant_id, workspace_id, and project_id are required")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"

class Store(Protocol):
    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None: ...
    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None: ...
    def append_event(self, event: dict[str, Any]) -> None: ...
    def put_sample(self, sample: dict[str, Any]) -> None: ...
    def list_samples(self, scope: Scope, kpi_name: str | None = None) -> list[dict[str, Any]]: ...
    def get_sample(self, sample_id: str, scope: Scope) -> dict[str, Any]: ...


class ReportingService:
    def __init__(self, store: Store):
        self.store = store

    def record_sample(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        kpi_name = str(payload.get("kpi_name") or "").strip()
        cohort = str(payload.get("cohort") or "").strip()
        value = payload.get("value")
        if not kpi_name or cohort not in {"with_astloom", "without_astloom"}:
            raise ValidationError("kpi_name and cohort(with_astloom|without_astloom) are required")
        if not isinstance(value, (int, float)):
            raise ValidationError("value must be numeric")
        existing = self.store.begin_idempotency(scope, idempotency_key, "kpi_sample")
        if existing:
            return self.store.get_sample(existing, scope)
        sample_id = _new_id("kpi")
        sample = {
            "id": sample_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "kpi_name": kpi_name,
            "cohort": cohort,
            "value": float(value),
            "unit": str(payload.get("unit") or "count"),
            "recorded_by": actor_id,
            "correlation_id": correlation_id,
            "created_at": _now(),
        }
        self.store.put_sample(sample)
        self.store.complete_idempotency(scope, idempotency_key, "kpi_sample", sample_id)
        self.store.append_event({"event_type": "kpi.sample_recorded", "sample_id": sample_id})
        return sample

    def compare(self, scope: Scope, kpi_name: str) -> dict[str, Any]:
        if not kpi_name.strip():
            raise ValidationError("kpi_name is required")
        samples = self.store.list_samples(scope, kpi_name=kpi_name)
        with_vals = [s["value"] for s in samples if s["cohort"] == "with_astloom"]
        without_vals = [s["value"] for s in samples if s["cohort"] == "without_astloom"]
        if not with_vals or not without_vals:
            raise ValidationError("both with_astloom and without_astloom samples are required")
        with_avg = sum(with_vals) / len(with_vals)
        without_avg = sum(without_vals) / len(without_vals)
        delta = with_avg - without_avg
        return {
            "kpi_name": kpi_name,
            "comparison_method": "with-or-without-astloom",
            "with_astloom_avg": with_avg,
            "without_astloom_avg": without_avg,
            "delta": delta,
            "sample_size": len(with_vals) + len(without_vals),
        }

    def benefit_summary(self, scope: Scope) -> dict[str, Any]:
        """Impact / quality / token benefit rollup across recorded KPI names."""
        samples = self.store.list_samples(scope)
        by_kpi: dict[str, list[dict[str, Any]]] = {}
        for sample in samples:
            by_kpi.setdefault(sample["kpi_name"], []).append(sample)
        comparisons: list[dict[str, Any]] = []
        for kpi_name, items in sorted(by_kpi.items()):
            with_vals = [s["value"] for s in items if s["cohort"] == "with_astloom"]
            without_vals = [s["value"] for s in items if s["cohort"] == "without_astloom"]
            if not with_vals or not without_vals:
                continue
            with_avg = sum(with_vals) / len(with_vals)
            without_avg = sum(without_vals) / len(without_vals)
            comparisons.append(
                {
                    "kpi_name": kpi_name,
                    "with_astloom_avg": with_avg,
                    "without_astloom_avg": without_avg,
                    "delta": with_avg - without_avg,
                    "sample_size": len(with_vals) + len(without_vals),
                }
            )
        token = next((c for c in comparisons if c["kpi_name"] in {"token_consumption", "tokens"}), None)
        quality = next((c for c in comparisons if c["kpi_name"] in {"quality_score", "quality"}), None)
        return {
            "comparison_method": "with-or-without-astloom",
            "kpi_count": len(comparisons),
            "comparisons": comparisons,
            "token_savings_delta": None if token is None else (token["without_astloom_avg"] - token["with_astloom_avg"]),
            "quality_delta": None if quality is None else quality["delta"],
        }
