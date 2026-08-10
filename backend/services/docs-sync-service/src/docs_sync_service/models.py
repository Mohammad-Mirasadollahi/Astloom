"""Docs-sync domain entities and value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .enums import DocumentState, DraftState, DriftState, DriftType, Severity
from .errors import ConflictError, ValidationError

REQUIRED_FRONTMATTER = (
    "doc_id",
    "title",
    "owner",
    "status",
    "schema_version",
    "linked_symbols",
    "decision_refs",
)


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    workspace_id: str
    project_id: str
    project_group_id: str | None = None

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.workspace_id.strip(), self.project_id.strip())):
            raise ValidationError("tenant_id, workspace_id, and project_id are required")


@dataclass
class CodeSymbol:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    repo: str
    file_path: str
    symbol_path: str
    kind: str
    signature_hash: str
    body_hash: str
    doc_required: bool
    tags: list[str]
    created_at: str
    updated_at: str
    version: int = 1

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "repo": self.repo,
            "file_path": self.file_path,
            "symbol_path": self.symbol_path,
            "kind": self.kind,
            "signature_hash": self.signature_hash,
            "body_hash": self.body_hash,
            "doc_required": self.doc_required,
            "tags": self.tags,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Document:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    path: str
    title: str
    owner: str
    state: DocumentState
    schema_version: str
    linked_symbols: list[str]
    decision_refs: list[str]
    frontmatter: dict[str, Any]
    body: str
    created_at: str
    updated_at: str
    version: int = 1

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "path": self.path,
            "title": self.title,
            "owner": self.owner,
            "state": self.state.value,
            "schema_version": self.schema_version,
            "linked_symbols": self.linked_symbols,
            "decision_refs": self.decision_refs,
            "frontmatter": self.frontmatter,
            "body": self.body,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class DocAnchor:
    id: str
    scope: Scope
    doc_id: str
    symbol_id: str
    recorded_hash: str
    status: str
    created_at: str
    updated_at: str
    version: int = 1

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "doc_id": self.doc_id,
            "symbol_id": self.symbol_id,
            "recorded_hash": self.recorded_hash,
            "status": self.status,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class DriftFinding:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    symbol_id: str
    doc_id: str | None
    drift_type: DriftType
    old_hash: str | None
    new_hash: str
    severity: Severity
    status: DriftState
    issue_ref: str
    task_ref: str | None
    evidence_refs: list[str]
    created_at: str
    updated_at: str
    version: int = 1

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "symbol_id": self.symbol_id,
            "doc_id": self.doc_id,
            "drift_type": self.drift_type.value,
            "old_hash": self.old_hash,
            "new_hash": self.new_hash,
            "severity": self.severity.value,
            "status": self.status.value,
            "issue_ref": self.issue_ref,
            "task_ref": self.task_ref,
            "evidence_refs": self.evidence_refs,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class DocumentationDraft:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    symbol_id: str
    finding_id: str | None
    title: str
    body: str
    state: DraftState
    created_at: str
    updated_at: str
    version: int = 1

    def approve(self, at: str) -> None:
        if self.state not in {DraftState.GENERATED, DraftState.WAITING_FOR_REVIEW}:
            raise ConflictError("draft is not approvable")
        self.state = DraftState.APPROVED
        self.version += 1
        self.updated_at = at

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "symbol_id": self.symbol_id,
            "finding_id": self.finding_id,
            "title": self.title,
            "body": self.body,
            "state": self.state.value,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
