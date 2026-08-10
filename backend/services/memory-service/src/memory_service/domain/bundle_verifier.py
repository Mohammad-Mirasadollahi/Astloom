"""
Role: Fail-closed ContextBundle prompt-context verification (GAP-T04).
SoT: Bundle public shape + candidate MemoryItems; digests from version/updated_at/body.
Allowed: return findings without mutating store; omit optional schema path when unavailable.
Forbidden: pass when scope leaks, restricted items are included, or high scorers vanish without exclusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from memory_service.core import (
    ContextBundle,
    MemoryItem,
    MemoryKind,
    MemoryState,
    Scope,
    WeightProfile,
    digest,
    estimate_tokens,
)

SCHEMA_REL = Path("backend/configs/schemas/context-bundle-audit.schema.json")

REF_MALFORMED = "malformed_source_ref"
SCOPE_MISMATCH = "scope_mismatch"
STALE_AFTER_BUILD = "stale_after_build"
OMITTED_CANDIDATE = "omitted_from_inclusion_and_exclusion"
OMITTED_HIGH_SCORER = "omitted_high_scorer"
RESTRICTED_INCLUDED = "restricted_memory_in_prompt"
TOKEN_OVERFLOW = "token_accounting_overflow"
TOKEN_MISMATCH = "token_estimate_mismatch"
MISSING_SOURCE_REFS = "missing_source_or_evidence_refs"
DUPLICATE_ID = "duplicate_bundle_id"
SCHEMA_INVALID = "schema_validation_failed"


@dataclass(frozen=True)
class VerificationFinding:
    code: str
    severity: str
    message: str
    memory_id: str | None = None


@dataclass(frozen=True)
class BundleVerificationResult:
    ok: bool
    findings: list[VerificationFinding] = field(default_factory=list)
    digests: dict[str, str] = field(default_factory=dict)
    used_tokens: int = 0
    audit: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "findings": [
                {
                    "code": f.code,
                    "severity": f.severity,
                    "message": f.message,
                    "memory_id": f.memory_id,
                }
                for f in self.findings
            ],
            "digests": self.digests,
            "used_tokens": self.used_tokens,
            "audit": self.audit,
        }


def memory_freshness_digest(item: MemoryItem | dict[str, Any]) -> str:
    if isinstance(item, MemoryItem):
        payload = {
            "id": item.id,
            "version": item.version,
            "updated_at": item.updated_at,
            "body": item.body,
            "state": item.state.value,
            "kind": item.kind.value,
        }
    else:
        payload = {
            "id": item.get("id"),
            "version": item.get("version"),
            "updated_at": item.get("updated_at"),
            "body": item.get("body"),
            "state": item.get("state"),
            "kind": item.get("kind"),
        }
    return digest(payload)


def _as_bundle_dict(bundle: ContextBundle | dict[str, Any]) -> dict[str, Any]:
    return bundle.public() if isinstance(bundle, ContextBundle) else dict(bundle)


def _candidate_map(candidates: list[MemoryItem] | list[dict[str, Any]]) -> dict[str, MemoryItem | dict[str, Any]]:
    out: dict[str, MemoryItem | dict[str, Any]] = {}
    for item in candidates:
        key = item.id if isinstance(item, MemoryItem) else str(item.get("id") or "")
        if key:
            out[key] = item
    return out


def _item_field(item: MemoryItem | dict[str, Any], name: str, default: Any = None) -> Any:
    if isinstance(item, MemoryItem):
        return getattr(item, name, default)
    return item.get(name, default)


def _refs_ok(refs: Any) -> tuple[bool, str | None]:
    if refs is None:
        return True, None
    if not isinstance(refs, list):
        return False, "refs must be a list"
    for ref in refs:
        if not isinstance(ref, str) or not ref.strip():
            return False, "ref must be a non-empty string"
        if any(ord(ch) < 32 for ch in ref):
            return False, "ref contains control characters"
    return True, None


def validate_bundle_schema(
    bundle_payload: dict[str, Any],
    *,
    schema_path: Path | None = None,
) -> list[str]:
    """Validate ContextBundle public shape against the audit JSON Schema. Returns error messages."""
    try:
        import jsonschema
    except ImportError:  # pragma: no cover — jsonschema is a test/runtime dep
        return ["jsonschema package is not installed"]

    path = schema_path
    if path is None:
        # .../backend/services/memory-service/src/memory_service/domain/this.py → repo root
        root = Path(__file__).resolve().parents[6]
        path = root / SCHEMA_REL
        if not path.is_file():
            path = Path.cwd() / SCHEMA_REL
    if not path.is_file():
        return [f"schema not found: {path}"]

    import json

    schema = json.loads(path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in sorted(validator.iter_errors(bundle_payload), key=lambda e: list(e.path))]


def verify_context_bundle(
    bundle: ContextBundle | dict[str, Any],
    *,
    expected_scope: Scope,
    candidates: list[MemoryItem] | list[dict[str, Any]],
    profile: WeightProfile | None = None,
    validate_schema: bool = True,
    schema_path: Path | None = None,
) -> BundleVerificationResult:
    """Verify a built ContextBundle against retrieval candidates (fail-closed on errors)."""
    payload = _as_bundle_dict(bundle)
    findings: list[VerificationFinding] = []
    digests: dict[str, str] = {}
    by_id = _candidate_map(candidates)

    if (
        payload.get("tenant_id") != expected_scope.tenant_id
        or payload.get("workspace_id") != expected_scope.workspace_id
        or payload.get("project_id") != expected_scope.project_id
    ):
        findings.append(
            VerificationFinding(
                SCOPE_MISMATCH,
                "error",
                "bundle scope does not match expected tenant/workspace/project",
            )
        )

    if validate_schema:
        for message in validate_bundle_schema(payload, schema_path=schema_path):
            findings.append(VerificationFinding(SCHEMA_INVALID, "error", message))

    items = list(payload.get("items") or [])
    excluded = list(payload.get("excluded") or [])
    included_ids: list[str] = []
    excluded_ids: list[str] = []
    used_tokens = 0
    budget = int(payload.get("token_budget") or 0)
    min_score = float(profile.min_relevance_score) if profile else None

    for entry in items:
        memory = entry.get("memory") if isinstance(entry, dict) else None
        if not isinstance(memory, dict):
            findings.append(
                VerificationFinding(SCHEMA_INVALID, "error", "included entry missing memory object")
            )
            continue
        mid = str(memory.get("id") or "")
        if not mid:
            findings.append(VerificationFinding(SCHEMA_INVALID, "error", "included memory missing id"))
            continue
        if mid in included_ids:
            findings.append(VerificationFinding(DUPLICATE_ID, "error", "duplicate included id", mid))
        included_ids.append(mid)

        if (
            memory.get("tenant_id") != expected_scope.tenant_id
            or memory.get("workspace_id") != expected_scope.workspace_id
            or memory.get("project_id") != expected_scope.project_id
        ):
            findings.append(
                VerificationFinding(SCOPE_MISMATCH, "error", "included memory scope mismatch", mid)
            )

        kind = memory.get("kind")
        state = memory.get("state")
        if kind == MemoryKind.RESTRICTED.value or state == MemoryState.RESTRICTED.value:
            findings.append(
                VerificationFinding(
                    RESTRICTED_INCLUDED,
                    "error",
                    "restricted memory must not enter prompt context",
                    mid,
                )
            )

        source_refs = memory.get("source_refs") or []
        evidence_refs = memory.get("evidence_refs") or []
        ok_src, err_src = _refs_ok(source_refs)
        ok_ev, err_ev = _refs_ok(evidence_refs)
        if not ok_src or not ok_ev:
            findings.append(
                VerificationFinding(
                    REF_MALFORMED,
                    "error",
                    err_src or err_ev or "malformed refs",
                    mid,
                )
            )
        elif not source_refs and not evidence_refs:
            findings.append(
                VerificationFinding(
                    MISSING_SOURCE_REFS,
                    "error",
                    "included memory requires source_refs or evidence_refs",
                    mid,
                )
            )

        candidate = by_id.get(mid)
        if candidate is not None:
            current_digest = memory_freshness_digest(candidate)
            digests[mid] = current_digest
            bundled_digest = memory_freshness_digest(memory)
            cand_version = int(_item_field(candidate, "version", 0) or 0)
            bundled_version = int(memory.get("version") or 0)
            if current_digest != bundled_digest or cand_version > bundled_version:
                findings.append(
                    VerificationFinding(
                        STALE_AFTER_BUILD,
                        "error",
                        "included memory changed after ContextBundle build",
                        mid,
                    )
                )

        estimate = int(entry.get("token_estimate") or 0)
        recomputed = estimate_tokens(str(memory.get("title") or "") + " " + str(memory.get("body") or ""))
        if estimate != recomputed:
            findings.append(
                VerificationFinding(
                    TOKEN_MISMATCH,
                    "error",
                    f"token_estimate {estimate} != recomputed {recomputed}",
                    mid,
                )
            )
        used_tokens += estimate

    for entry in excluded:
        if not isinstance(entry, dict):
            findings.append(VerificationFinding(SCHEMA_INVALID, "error", "excluded entry must be object"))
            continue
        mid = str(entry.get("id") or "")
        if not mid:
            findings.append(VerificationFinding(SCHEMA_INVALID, "error", "excluded entry missing id"))
            continue
        if mid in excluded_ids:
            findings.append(VerificationFinding(DUPLICATE_ID, "error", "duplicate excluded id", mid))
        excluded_ids.append(mid)
        if mid in included_ids:
            findings.append(
                VerificationFinding(
                    DUPLICATE_ID,
                    "error",
                    "memory appears in both items and excluded",
                    mid,
                )
            )
        if not entry.get("reason"):
            findings.append(
                VerificationFinding(
                    OMITTED_HIGH_SCORER,
                    "error",
                    "excluded entry missing reason",
                    mid,
                )
            )

    candidate_ids = set(by_id)
    accounted = set(included_ids) | set(excluded_ids)
    for mid in sorted(candidate_ids - accounted):
        candidate = by_id[mid]
        kind = _item_field(candidate, "kind")
        kind_val = kind.value if isinstance(kind, MemoryKind) else str(kind or "")
        entry_score = float(candidate["score"]) if isinstance(candidate, dict) and "score" in candidate else None
        state = _item_field(candidate, "state")
        state_val = state.value if isinstance(state, MemoryState) else str(state or "")
        looks_eligible = state_val not in {
            MemoryState.RESTRICTED.value,
            MemoryState.STALE.value,
            MemoryState.DEPRECATED.value,
            MemoryState.ARCHIVED.value,
        } and kind_val not in {
            MemoryKind.RESTRICTED.value,
            MemoryKind.DEPRECATED.value,
        }
        if (
            min_score is not None
            and entry_score is not None
            and entry_score >= min_score
            and looks_eligible
        ):
            findings.append(
                VerificationFinding(
                    OMITTED_HIGH_SCORER,
                    "error",
                    f"high-scoring candidate ({entry_score}) omitted without exclusion reason",
                    mid,
                )
            )
        else:
            findings.append(
                VerificationFinding(
                    OMITTED_CANDIDATE,
                    "error",
                    "candidate missing from items and excluded",
                    mid,
                )
            )

    if budget > 0 and used_tokens > budget:
        findings.append(
            VerificationFinding(
                TOKEN_OVERFLOW,
                "error",
                f"used_tokens {used_tokens} exceeds token_budget {budget}",
            )
        )

    errors = [f for f in findings if f.severity == "error"]
    audit = {
        "bundle_id": payload.get("bundle_id"),
        "scope": {
            "tenant_id": expected_scope.tenant_id,
            "workspace_id": expected_scope.workspace_id,
            "project_id": expected_scope.project_id,
        },
        "included_ids": included_ids,
        "excluded_ids": excluded_ids,
        "candidate_count": len(by_id),
        "weight_profile": payload.get("weight_profile"),
        "prompt_cache": payload.get("prompt_cache"),
        "built_at": payload.get("built_at"),
        "checks": [
            "scope",
            "source_refs",
            "freshness_digests",
            "inclusion_exclusion_completeness",
            "token_accounting",
        ],
    }
    return BundleVerificationResult(
        ok=not errors,
        findings=findings,
        digests=digests,
        used_tokens=used_tokens,
        audit=audit,
    )
