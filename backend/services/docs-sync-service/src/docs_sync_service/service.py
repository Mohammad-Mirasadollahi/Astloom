"""Docs-sync application service (index, drift, coverage, CI gate).

Role: orchestrate Store mutations and outbox events for symbols/docs/anchors.
Source of truth: Store + outbox events; bloom cache is derived coverage hint.
Allowed: soft per-command idempotency; thread-safe bloom rebuild.
Forbidden: inventing edges/anchors without Store rows; duplicate natural-key
anchors; resetting entity versions during an update.
"""

from __future__ import annotations

import threading
from typing import Any
from uuid import uuid4

from .bloom import BloomFilter
from .enums import DocumentState, DraftState, DriftState, DriftType, Severity
from .errors import ConflictError, NotFoundError, ValidationError
from .models import (
    REQUIRED_FRONTMATTER,
    CodeSymbol,
    DocAnchor,
    Document,
    DocumentationDraft,
    DriftFinding,
    Scope,
)
from .ports import Store
from .util import digest, normalize_source, now, sanitize, severity_for


class DocsSyncService:
    def __init__(self, store: Store):
        self.store = store
        self._bloom: dict[str, BloomFilter] = {}
        self._bloom_lock = threading.RLock()

    def index_symbol(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> CodeSymbol:
        self._require_key(key)
        payload = sanitize(payload)
        missing = [field for field in ("repo", "file_path", "symbol_path", "kind", "body") if not payload.get(field)]
        if missing:
            raise ValidationError("missing required fields: " + ", ".join(missing))
        normalized_body = normalize_source(payload["body"])
        signature = payload.get("signature") or payload["symbol_path"]
        command_payload = {
            "repo": payload["repo"],
            "file_path": payload["file_path"],
            "symbol_path": payload["symbol_path"],
            "kind": payload["kind"],
            "signature": signature,
            "body": normalized_body,
            "doc_required": bool(payload.get("doc_required", True)),
            "tags": sorted(set(payload.get("tags") or [])),
        }
        prior = self.store.idempotent(scope, "index_symbol", key, command_payload)
        if prior:
            return self.store.get_symbol(prior, scope)
        timestamp = now()
        existing = self.store.find_symbol(
            scope, command_payload["repo"], command_payload["file_path"], command_payload["symbol_path"]
        )
        if existing:
            existing.kind = command_payload["kind"]
            existing.signature_hash = digest(signature)
            existing.body_hash = digest(normalized_body)
            existing.doc_required = command_payload["doc_required"]
            existing.tags = command_payload["tags"]
            existing.version += 1
            existing.updated_at = timestamp
            existing.actor_id = actor
            existing.correlation_id = correlation_id
            symbol = existing
        else:
            symbol = CodeSymbol(
                str(uuid4()),
                scope,
                actor,
                correlation_id,
                command_payload["repo"],
                command_payload["file_path"],
                command_payload["symbol_path"],
                command_payload["kind"],
                digest(signature),
                digest(normalized_body),
                command_payload["doc_required"],
                command_payload["tags"],
                timestamp,
                timestamp,
            )
        self.store.put_symbol(symbol)
        self.store.remember(scope, "index_symbol", key, command_payload, symbol.id)
        self.emit("SymbolIndexed", symbol.public(), scope, actor, correlation_id, key, symbol.id, [])
        return symbol

    def unregister_symbol(self, scope: Scope, symbol_id: str) -> None:
        """Remove a docs-sync symbol registry row (and its anchors) from this scope."""
        sid = str(symbol_id or "").strip()
        if not sid:
            raise ValidationError("symbol_id is required")
        self.store.delete_symbol(sid, scope)

    def validate_frontmatter(self, frontmatter: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not isinstance(frontmatter, dict):
            return ["frontmatter must be an object"]
        for field_name in REQUIRED_FRONTMATTER:
            if field_name not in frontmatter:
                errors.append(f"missing required field: {field_name}")
        if "linked_symbols" in frontmatter and not isinstance(frontmatter["linked_symbols"], list):
            errors.append("linked_symbols must be a list")
        if "decision_refs" in frontmatter and not isinstance(frontmatter["decision_refs"], list):
            errors.append("decision_refs must be a list")
        if frontmatter.get("owner") is not None and not str(frontmatter.get("owner") or "").strip():
            errors.append("owner must be non-empty")
        if frontmatter.get("status") not in {None, "draft", "active", "deprecated", "archived"}:
            errors.append("invalid status")
        return errors

    def index_document(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> Document:
        self._require_key(key)
        payload = sanitize(payload)
        if not payload.get("path"):
            raise ValidationError("path is required")
        frontmatter = payload.get("frontmatter") or {}
        errors = self.validate_frontmatter(frontmatter)
        if errors:
            raise ValidationError("frontmatter validation failed: " + "; ".join(errors))
        command_payload = {
            "path": payload["path"],
            "frontmatter": frontmatter,
            "body": payload.get("body") or "",
        }
        prior = self.store.idempotent(scope, "index_document", key, command_payload)
        if prior:
            return self.store.get_document(prior, scope)
        timestamp = now()
        document_id = str(frontmatter.get("doc_id") or uuid4())
        try:
            document = self.store.get_document(document_id, scope)
        except NotFoundError:
            document = Document(
                document_id,
                scope,
                actor,
                correlation_id,
                command_payload["path"],
                str(frontmatter["title"]),
                str(frontmatter["owner"]),
                DocumentState.VALID,
                str(frontmatter["schema_version"]),
                list(frontmatter.get("linked_symbols") or []),
                list(frontmatter.get("decision_refs") or []),
                dict(frontmatter),
                command_payload["body"],
                timestamp,
                timestamp,
            )
        else:
            document.actor_id = actor
            document.correlation_id = correlation_id
            document.path = command_payload["path"]
            document.title = str(frontmatter["title"])
            document.owner = str(frontmatter["owner"])
            document.state = DocumentState.VALID
            document.schema_version = str(frontmatter["schema_version"])
            document.linked_symbols = list(frontmatter.get("linked_symbols") or [])
            document.decision_refs = list(frontmatter.get("decision_refs") or [])
            document.frontmatter = dict(frontmatter)
            document.body = command_payload["body"]
            document.updated_at = timestamp
            document.version += 1
        self.store.put_document(document)
        self.store.remember(scope, "index_document", key, command_payload, document.id)
        self.emit("DocumentIndexed", document.public(), scope, actor, correlation_id, key, document.id, [])
        return document

    def register_anchor(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> DocAnchor:
        self._require_key(key)
        payload = sanitize(payload)
        missing = [field for field in ("doc_id", "symbol_id", "recorded_hash") if not payload.get(field)]
        if missing:
            raise ValidationError("missing required fields: " + ", ".join(missing))
        document = self.store.get_document(payload["doc_id"], scope)
        if document.state == DocumentState.INVALID_FRONTMATTER:
            raise ConflictError("cannot anchor an invalid document")
        symbol = self.store.get_symbol(payload["symbol_id"], scope)
        command_payload = {
            "doc_id": payload["doc_id"],
            "symbol_id": payload["symbol_id"],
            "recorded_hash": payload["recorded_hash"],
        }
        prior = self.store.idempotent(scope, "register_anchor", key, command_payload)
        if prior:
            return self.store.get_anchor(prior, scope)
        timestamp = now()
        status = "synced" if payload["recorded_hash"] == symbol.body_hash else "stale"
        natural = [
            item
            for item in self.store.list_anchors(scope, payload["symbol_id"])
            if item.doc_id == payload["doc_id"]
        ]
        if natural:
            anchor = natural[-1]
            anchor.recorded_hash = payload["recorded_hash"]
            anchor.status = status
            anchor.updated_at = timestamp
            anchor.version += 1
            for duplicate in natural[:-1]:
                self.store.delete_anchor(duplicate.id, scope)
        else:
            anchor_id = "anchor:" + digest(
                {
                    "tenant_id": scope.tenant_id,
                    "workspace_id": scope.workspace_id,
                    "project_id": scope.project_id,
                    "doc_id": payload["doc_id"],
                    "symbol_id": payload["symbol_id"],
                }
            )
            anchor = DocAnchor(
                anchor_id,
                scope,
                payload["doc_id"],
                payload["symbol_id"],
                payload["recorded_hash"],
                status,
                timestamp,
                timestamp,
            )
        self.store.put_anchor(anchor)
        self.store.remember(scope, "register_anchor", key, command_payload, anchor.id)
        self._rebuild_bloom(scope)
        self.emit("AnchorRegistered", anchor.public(), scope, actor, correlation_id, key, anchor.id, [])
        self.emit("DocCoverageChanged", self.get_doc_coverage(scope), scope, actor, correlation_id, key, anchor.id, [])
        return anchor

    def detect_drift(self, scope: Scope, actor: str, correlation_id: str, key: str, symbol_ids: list[str] | None = None) -> list[DriftFinding]:
        self._require_key(key)
        payload = {"symbol_ids": sorted(symbol_ids or [])}
        prior = self.store.idempotent(scope, "detect_drift", key, payload)
        if prior:
            return [self.store.get_finding(item_id, scope) for item_id in prior.split(",") if item_id]
        symbols = self.store.list_symbols(scope)
        if symbol_ids:
            wanted = set(symbol_ids)
            symbols = [symbol for symbol in symbols if symbol.id in wanted]
        findings: list[DriftFinding] = []
        timestamp = now()
        for symbol in symbols:
            anchors = self.store.list_anchors(scope, symbol.id)
            if symbol.doc_required and not anchors:
                findings.append(self._create_finding(scope, actor, correlation_id, symbol, None, DriftType.MISSING_DOC, None, symbol.body_hash, timestamp))
                continue
            for anchor in anchors:
                if anchor.recorded_hash != symbol.body_hash:
                    anchor.status = "stale"
                    anchor.version += 1
                    anchor.updated_at = timestamp
                    self.store.put_anchor(anchor)
                    findings.append(
                        self._create_finding(
                            scope,
                            actor,
                            correlation_id,
                            symbol,
                            anchor.doc_id,
                            DriftType.STALE_DOC,
                            anchor.recorded_hash,
                            symbol.body_hash,
                            timestamp,
                        )
                    )
                else:
                    anchor.status = "synced"
                    self.store.put_anchor(anchor)
        if not findings:
            self.store.remember(scope, "detect_drift", key, payload, "")
            return []
        joined = ",".join(finding.id for finding in findings)
        self.store.remember(scope, "detect_drift", key, payload, joined)
        return findings

    def create_draft(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> DocumentationDraft:
        self._require_key(key)
        payload = sanitize(payload)
        if not payload.get("symbol_id") or not payload.get("title") or not payload.get("body"):
            raise ValidationError("symbol_id, title, and body are required")
        self.store.get_symbol(payload["symbol_id"], scope)
        command_payload = {
            "symbol_id": payload["symbol_id"],
            "title": payload["title"],
            "body": payload["body"],
            "finding_id": payload.get("finding_id"),
        }
        prior = self.store.idempotent(scope, "create_draft", key, command_payload)
        if prior:
            return self.store.get_draft(prior, scope)
        timestamp = now()
        draft = DocumentationDraft(
            str(uuid4()),
            scope,
            actor,
            correlation_id,
            command_payload["symbol_id"],
            command_payload.get("finding_id"),
            command_payload["title"],
            command_payload["body"],
            DraftState.WAITING_FOR_REVIEW,
            timestamp,
            timestamp,
        )
        self.store.put_draft(draft)
        self.store.remember(scope, "create_draft", key, command_payload, draft.id)
        self.emit("DocumentationDraftCreated", draft.public(), scope, actor, correlation_id, key, draft.id, [])
        return draft

    def approve_draft(self, scope: Scope, actor: str, correlation_id: str, key: str, draft_id: str) -> DocumentationDraft:
        self._require_key(key)
        payload = {"draft_id": draft_id}
        prior = self.store.idempotent(scope, "approve_draft", key, payload)
        if prior:
            return self.store.get_draft(prior, scope)
        draft = self.store.get_draft(draft_id, scope)
        draft.approve(now())
        self.store.put_draft(draft)
        self.store.remember(scope, "approve_draft", key, payload, draft.id)
        self.emit("DocumentationDraftApproved", draft.public(), scope, actor, correlation_id, key, draft.id, [])
        return draft

    def find_docs_for_symbol(self, scope: Scope, symbol_id: str) -> list[Document]:
        self.store.get_symbol(symbol_id, scope)
        doc_ids = {anchor.doc_id for anchor in self.store.list_anchors(scope, symbol_id)}
        return [document for document in self.store.list_documents(scope) if document.id in doc_ids]

    def list_drift_findings(self, scope: Scope) -> list[DriftFinding]:
        return self.store.list_findings(scope)

    def get_doc_coverage(self, scope: Scope) -> dict[str, Any]:
        symbols = self.store.list_symbols(scope)
        entries = []
        documented = 0
        required = 0
        for symbol in symbols:
            has_doc = bool(self.store.list_anchors(scope, symbol.id))
            if symbol.doc_required:
                required += 1
                if has_doc:
                    documented += 1
            entries.append(
                {
                    "symbol_id": symbol.id,
                    "symbol_path": symbol.symbol_path,
                    "doc_required": symbol.doc_required,
                    "has_doc": has_doc,
                    "lookup_source": "graph",
                }
            )
        if required == 0:
            return {
                "required_symbols": 0,
                "documented_symbols": 0,
                "coverage_ratio": None,
                "empty_reason": "no_required_symbols_registered",
                "entries": entries,
            }
        return {
            "required_symbols": required,
            "documented_symbols": documented,
            "coverage_ratio": round(documented / required, 3),
            "empty_reason": None,
            "entries": entries,
        }

    def explain_doc_impact(self, scope: Scope, symbol_id: str) -> dict[str, Any]:
        symbol = self.store.get_symbol(symbol_id, scope)
        anchors = self.store.list_anchors(scope, symbol_id)
        findings = [finding for finding in self.store.list_findings(scope) if finding.symbol_id == symbol_id]
        return {
            "symbol": symbol.public(),
            "severity": severity_for(symbol).value,
            "anchors": [anchor.public() for anchor in anchors],
            "findings": [finding.public() for finding in findings],
            "bloom_maybe_documented": self.bloom_lookup(scope, symbol_id)["maybe_documented"],
        }

    def find_missing_docs(self, scope: Scope) -> list[dict[str, Any]]:
        missing = []
        for symbol in self.store.list_symbols(scope):
            if symbol.doc_required and not self.store.list_anchors(scope, symbol.id):
                missing.append({"symbol": symbol.public(), "severity": severity_for(symbol).value})
        return missing

    def stale_candidates(
        self,
        scope: Scope,
        *,
        scope_mode: str,
        anchor_symbols: list[str] | None = None,
        anchor_paths: list[str] | None = None,
        max_results: int = 50,
        include_uncertain: bool = False,
        min_confidence: float | None = None,
        path_prefix: str | None = None,
        include_coverage_gaps: bool = False,
        freshness: str = "ok",
    ) -> dict[str, Any]:
        """Scored stale-documentation candidates (Astloom does not delete Markdown)."""
        from .domain.stale_docs import find_stale_doc_candidates

        return find_stale_doc_candidates(
            self.store.list_documents(scope),
            self.store.list_symbols(scope),
            self.store.list_anchors(scope),
            scope_mode=scope_mode,
            anchor_symbols=anchor_symbols,
            anchor_paths=anchor_paths,
            max_results=max_results,
            include_uncertain=include_uncertain,
            freshness=freshness,
            min_confidence=min_confidence,
            path_prefix=path_prefix,
            include_coverage_gaps=include_coverage_gaps,
        )

    def bloom_lookup(self, scope: Scope, symbol_id: str) -> dict[str, Any]:
        bloom = self._bloom_for(scope)
        maybe = bloom.might_contain(symbol_id)
        verified = bool(self.store.list_anchors(scope, symbol_id)) if maybe else False
        return {
            "symbol_id": symbol_id,
            "filter_version": bloom.version,
            "maybe_documented": maybe,
            "verified_has_doc": verified if maybe else False,
            "definite_no_doc": not maybe,
        }

    def evaluate_ci_gate(self, scope: Scope, waived_finding_ids: list[str] | None = None) -> dict[str, Any]:
        waived = set(waived_finding_ids or [])
        findings = [finding for finding in self.store.list_findings(scope) if finding.status != DriftState.FIXED]
        blockers = []
        warnings = []
        for finding in findings:
            if finding.id in waived:
                continue
            if finding.severity == Severity.CRITICAL:
                blockers.append(finding.public())
            elif finding.severity == Severity.HIGH:
                blockers.append(finding.public())
            elif finding.severity == Severity.MEDIUM:
                warnings.append(finding.public())
        decision = "fail" if blockers else "pass"
        return {
            "decision": decision,
            "blockers": blockers,
            "warnings": warnings,
            "waived_finding_ids": sorted(waived),
        }

    def _create_finding(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        symbol: CodeSymbol,
        doc_id: str | None,
        drift_type: DriftType,
        old_hash: str | None,
        new_hash: str,
        timestamp: str,
    ) -> DriftFinding:
        severity = severity_for(symbol)
        finding_id = str(uuid4())
        actionable = severity in {Severity.HIGH, Severity.CRITICAL} or drift_type == DriftType.MISSING_DOC
        finding = DriftFinding(
            finding_id,
            scope,
            actor,
            correlation_id,
            symbol.id,
            doc_id,
            drift_type,
            old_hash,
            new_hash,
            severity,
            DriftState.TASK_CREATED if actionable else DriftState.DETECTED,
            f"issue:{finding_id}",
            f"task:docs-agent:{finding_id}" if actionable else None,
            [symbol.id] + ([doc_id] if doc_id else []),
            timestamp,
            timestamp,
        )
        self.store.put_finding(finding)
        self.emit("DocumentationDriftDetected", finding.public(), scope, actor, correlation_id, "", finding.id, finding.evidence_refs)
        return finding

    def _rebuild_bloom(self, scope: Scope) -> BloomFilter:
        bloom = BloomFilter(version=digest(scope.project_id + now())[:12])
        for anchor in self.store.list_anchors(scope):
            bloom.add(anchor.symbol_id)
        with self._bloom_lock:
            self._bloom[self._scope_key(scope)] = bloom
        return bloom

    def _bloom_for(self, scope: Scope) -> BloomFilter:
        key = self._scope_key(scope)
        with self._bloom_lock:
            existing = self._bloom.get(key)
        if existing is not None:
            return existing
        return self._rebuild_bloom(scope)

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id))

    def _require_key(self, key: str) -> None:
        if not key:
            raise ValidationError("Idempotency-Key header is required")

    def emit(self, event_type: str, payload: dict[str, Any], scope: Scope, actor: str, correlation_id: str, key: str, causation_id: str, evidence_refs: list[str]) -> None:
        self.store.event(
            {
                "event_id": str(uuid4()),
                "event_type": event_type,
                "event_version": 1,
                "occurred_at": now(),
                "producer": "docs-sync-service",
                "tenant_id": scope.tenant_id,
                "workspace_id": scope.workspace_id,
                "project_id": scope.project_id,
                "project_group_id": scope.project_group_id,
                "actor_ref": actor,
                "correlation_id": correlation_id,
                "causation_id": causation_id,
                "idempotency_key": key,
                "payload": payload,
                "evidence_refs": evidence_refs,
            }
        )
