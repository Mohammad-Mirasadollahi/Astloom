"""Backup scope identity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Scope:
    tenant_id: str
    workspace_id: str
    project_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
        }

    def validate(self) -> None:
        for name, value in (
            ("tenant_id", self.tenant_id),
            ("workspace_id", self.workspace_id),
            ("project_id", self.project_id),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} is required")


@dataclass(frozen=True, slots=True)
class Remap:
    tenant_id: str | None = None
    workspace_id: str | None = None
    project_id: str | None = None

    def apply(self, scope: Scope) -> Scope:
        return Scope(
            tenant_id=self.tenant_id or scope.tenant_id,
            workspace_id=self.workspace_id or scope.workspace_id,
            project_id=self.project_id or scope.project_id,
        )

    @property
    def active(self) -> bool:
        return bool(self.tenant_id or self.workspace_id or self.project_id)
