"""Numeric confidence and evidence for dead-code candidates.

Role: Score unused-symbol / unreachable-file / dead-subgraph findings from graph
evidence; wire optional coverage, disk string-search, local triage, and flag ports
without inventing safe_to_delete.
Source of truth: docs/07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md
Allowed: monotonic score decreases via caps; attach evidence; classify tiers.
Forbidden: raising confidence from weak signals; Astloom never deletes code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .confidence_policy import parse_call_confidence
from .enums import CallConfidence, RelType

# Proof-of-live edge types (absence of these from live roots ⇒ candidate).
USE_EDGE_TYPES = frozenset(
    {
        RelType.CALLS.value,
        RelType.IMPORTS.value,
        RelType.HTTP_CALLS.value,
        RelType.ASYNC_CALLS.value,
        RelType.ROUTES_TO.value,
    }
)

_STRONG_CONFIDENCE = frozenset({CallConfidence.EXACT, CallConfidence.PROBABLE, CallConfidence.EXTERNAL})
_WEAK_CONFIDENCE = frozenset({CallConfidence.AMBIGUOUS, CallConfidence.UNRESOLVED})

_HARD_BLOCKERS = frozenset(
    {
        "entrypoint",
        "public_http_handler",
        "possible_string_registry",
        "tsoc_defer",
        "external_symbol",
        "string_name_reference",
        "coverage_runtime_use",
    }
)

_RUNTIME_PATH_RISK = re.compile(
    r"(^|/)(config|settings|env|bootstrap|startup|entrypoint|database|db|schema|seed|migration|"
    r"scripts|bin|tasks)(/|$)",
    re.IGNORECASE,
)

_WIP_PATH = re.compile(
    r"(^|/)(wip|tmp|temp|scratch|experimental|draft)(/|$)",
    re.IGNORECASE,
)

_DYNAMIC_LOADER_HINT = re.compile(
    r"importlib\.(?:import_module|reload)|__import__\s*\(|pkgutil\.iter_modules|"
    r"\bimport\s*\(|require\.context\(|import\.meta\.glob\(|React\.lazy\(",
    re.IGNORECASE,
)

_QUOTED_NAME = re.compile(r"""['"`]([A-Za-z_][\w]{1,})['"`]""")

TIER_HIGH = 0.80
TIER_MEDIUM = 0.50


@dataclass(frozen=True)
class StringNameCorpus:
    """Quoted-name → file paths index for SCARF-style soft blockers.

    Built once per unused-candidates scan so lookups stay O(hits) instead of
    re-walking every symbol body for each dead candidate.
    """

    name_to_paths: dict[str, tuple[str, ...]]

    @classmethod
    def from_symbols(cls, symbols: Iterable[Any]) -> "StringNameCorpus":
        buckets: dict[str, list[str]] = {}
        seen_files: set[str] = set()
        for sym in symbols:
            path = (getattr(sym, "file_path", "") or "").replace("\\", "/")
            if not path or path in seen_files:
                continue
            seen_files.add(path)
            blob = f"{getattr(sym, 'signature', '')}\n{getattr(sym, 'body', '')}"
            found: set[str] = set()
            for match in _QUOTED_NAME.finditer(blob):
                found.add(match.group(1))
            for name in found:
                buckets.setdefault(name, []).append(path)
        return cls(name_to_paths={k: tuple(v) for k, v in buckets.items()})

    def hits(self, symbol_name: str, file_path: str, *, max_hits: int = 5) -> list[str]:
        name = (symbol_name or "").strip()
        if len(name) < 2:
            return []
        defining = (file_path or "").replace("\\", "/")
        out: list[str] = []
        for other in self.name_to_paths.get(name, ()):
            if other == defining:
                continue
            out.append(other)
            if len(out) >= max_hits:
                break
        return out


def directories_with_dynamic_loaders(symbols: Iterable[Any]) -> set[str]:
    """Parent directories whose indexed bodies look like dynamic loaders."""
    tainted: set[str] = set()
    seen_files: set[str] = set()
    for sym in symbols:
        path = (getattr(sym, "file_path", "") or "").replace("\\", "/")
        if not path or path in seen_files:
            continue
        seen_files.add(path)
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        if parent in tainted:
            continue
        blob = f"{getattr(sym, 'signature', '')}\n{getattr(sym, 'body', '')[:800]}"
        if blob_has_dynamic_loader(blob):
            tainted.add(parent)
    return tainted


def blob_has_dynamic_loader(blob: str) -> bool:
    return bool(_DYNAMIC_LOADER_HINT.search(blob or ""))


def graph_corpus_string_name_hits(
    symbols: Iterable[Any],
    symbol_name: str,
    file_path: str,
    *,
    max_hits: int = 5,
    corpus: StringNameCorpus | None = None,
) -> list[str]:
    """SCARF-style soft evidence: quoted name appears in another indexed file body.

    Uses the in-memory CKG corpus (signature + body). Not a disk BigGrep; still
    enough to soft-block ``safe_to_delete`` when registries hold string names.
    Prefer a prebuilt ``StringNameCorpus`` for multi-candidate scans.
    """
    if corpus is not None:
        return corpus.hits(symbol_name, file_path, max_hits=max_hits)
    name = (symbol_name or "").strip()
    if len(name) < 2:
        return []
    defining = (file_path or "").replace("\\", "/")
    needles = (f"'{name}'", f'"{name}"', f"`{name}`")
    hits: list[str] = []
    seen: set[str] = set()
    for sym in symbols:
        other = (getattr(sym, "file_path", "") or "").replace("\\", "/")
        if not other or other == defining or other in seen:
            continue
        blob = f"{getattr(sym, 'signature', '')}\n{getattr(sym, 'body', '')}"
        if any(n in blob for n in needles):
            seen.add(other)
            hits.append(other)
            if len(hits) >= max_hits:
                break
    return hits


@dataclass(frozen=True)
class Evidence:
    kind: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "detail": self.detail}


@dataclass
class ScoreInput:
    visibility: str = "public"
    blockers: list[str] = field(default_factory=list)
    freshness: str = "ok"
    finding_kind: str = "unused_symbol"
    test_only: bool = False
    file_has_live_importers: bool = False
    weak_call_edges: bool = False
    dynamic_loader_nearby: bool = False
    path_risk: bool = False
    wip_path: bool = False
    coverage_hits: int | None = None
    days_since_touch: int | None = None


@dataclass
class ScoreResult:
    score: float
    tier: str
    evidence: list[Evidence]
    safe_to_delete: bool
    blockers: list[str] = field(default_factory=list)

    def to_row_fields(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "confidence": self.tier,
            "evidence": [e.to_dict() for e in self.evidence],
            "safe_to_delete": self.safe_to_delete,
            "blockers": list(self.blockers),
        }


def tier_for_score(score: float) -> str:
    if score >= TIER_HIGH:
        return "high"
    if score >= TIER_MEDIUM:
        return "medium"
    return "low"


def edge_confidence(edge: Any) -> CallConfidence:
    return parse_call_confidence(getattr(edge, "confidence", None))


def is_strong_use_edge(edge: Any) -> bool:
    if getattr(edge, "rel_type", None) not in USE_EDGE_TYPES:
        return False
    # IMPORTS / ROUTES_TO without call confidence still count as structural use.
    rel = edge.rel_type
    if rel in {RelType.IMPORTS.value, RelType.ROUTES_TO.value}:
        conf = edge_confidence(edge)
        return conf not in _WEAK_CONFIDENCE
    return edge_confidence(edge) in _STRONG_CONFIDENCE


def is_weak_use_edge(edge: Any) -> bool:
    if getattr(edge, "rel_type", None) not in USE_EDGE_TYPES:
        return False
    return edge_confidence(edge) in _WEAK_CONFIDENCE


def path_has_runtime_load_risk(file_path: str) -> bool:
    path = (file_path or "").replace("\\", "/")
    return bool(_RUNTIME_PATH_RISK.search(path))


def path_looks_wip(file_path: str) -> bool:
    path = (file_path or "").replace("\\", "/")
    return bool(_WIP_PATH.search(path))


def score_candidate(inp: ScoreInput) -> ScoreResult:
    """Monotonic confidence score: start from a base, only decrease via caps."""
    evidence: list[Evidence] = [
        Evidence("unreachable_from_live_roots"),
        Evidence("no_inbound_strong_use"),
    ]
    if inp.finding_kind == "unreachable_file":
        evidence.append(Evidence("unreachable_file"))
        base = 0.70
    elif inp.finding_kind == "zombie_package":
        evidence.append(Evidence("zombie_package"))
        base = 0.70
    elif inp.finding_kind == "unwired_shared_package":
        evidence.append(Evidence("unwired_shared_package"))
        base = 0.65
    elif inp.finding_kind == "runtime_dead":
        evidence.append(Evidence("runtime_dead"))
        base = 0.45
    elif inp.finding_kind == "dead_subgraph":
        evidence.append(Evidence("dead_subgraph_member"))
        # Subgraph members follow visibility; private still needs live importers for 0.95.
        if (inp.visibility or "").lower() in {"private", "protected", "internal"} and inp.file_has_live_importers:
            base = 0.95
            evidence.append(Evidence("file_has_live_importers"))
        elif (inp.visibility or "").lower() in {"private", "protected", "internal"}:
            base = 0.80
        else:
            base = 0.80
    elif (inp.visibility or "").lower() in {"private", "protected", "internal"}:
        # Normative: 0.95 only when the containing file has other live importers.
        if inp.file_has_live_importers:
            base = 0.95
            evidence.append(Evidence("file_has_live_importers"))
        else:
            base = 0.80
    else:
        base = 0.80

    score = base
    blockers = list(inp.blockers)

    if inp.wip_path:
        evidence.append(Evidence("wip_or_recent_path"))
        score = min(score, 0.55)

    if inp.test_only:
        evidence.append(Evidence("test_only"))
        score = min(score, 0.45)
        blockers = list(dict.fromkeys([*blockers, "test_only"]))

    if inp.weak_call_edges:
        evidence.append(Evidence("weak_or_ambiguous_call_edge"))
        score = min(score, 0.55)

    if inp.dynamic_loader_nearby:
        evidence.append(Evidence("dynamic_import_nearby"))
        score = min(score, 0.40)
        blockers = list(dict.fromkeys([*blockers, "dynamic_import_nearby"]))

    if inp.path_risk:
        evidence.append(Evidence("runtime_load_path_risk"))
        score = min(score, 0.40)
        blockers = list(dict.fromkeys([*blockers, "runtime_load_path_risk"]))

    # Coverage / runtime confirmation (optional ingest): hits block delete; zero only evidences.
    if inp.coverage_hits is not None:
        if inp.coverage_hits > 0:
            evidence.append(Evidence("coverage_has_hits", f"hits={inp.coverage_hits}"))
            score = min(score, 0.40)
            blockers = list(dict.fromkeys([*blockers, "coverage_runtime_use"]))
        else:
            evidence.append(Evidence("coverage_zero_hits"))

    # Phase-2 string-name soft-blocker: cap at 0.45 (normative table), still hard for safe_to_delete.
    if "string_name_reference" in blockers:
        evidence.append(Evidence("string_name_reference"))
        score = min(score, 0.45)

    other_hard = [b for b in blockers if b in _HARD_BLOCKERS and b != "string_name_reference"]
    if other_hard:
        score = min(score, 0.40)
        evidence.append(Evidence("hard_blocker", ",".join(sorted(set(other_hard)))))

    if inp.freshness in {"stale", "pending_sync"}:
        evidence.append(Evidence(f"freshness_{inp.freshness}"))
        score = min(score, 0.50)

    # Normative: scores only decrease via caps (no age uplift).
    if inp.days_since_touch is not None and inp.days_since_touch < 30:
        score = min(score, 0.55)
        evidence.append(Evidence("recent_file_cap", f"days={inp.days_since_touch}"))
        blockers = list(dict.fromkeys([*blockers, "recent_file_cap"]))

    score = round(max(0.0, min(1.0, score)), 4)
    tier = tier_for_score(score)
    hard_present = bool([b for b in blockers if b in _HARD_BLOCKERS])
    safe = (
        score >= TIER_HIGH
        and not hard_present
        and not inp.test_only
        and inp.freshness == "ok"
        and not inp.dynamic_loader_nearby
        and not inp.path_risk
        and inp.finding_kind
        not in {"zombie_package", "unwired_shared_package", "runtime_dead", "flag_controlled_dead"}
    )
    if safe:
        evidence.append(Evidence("freshness_ok"))
    return ScoreResult(
        score=score,
        tier=tier,
        evidence=evidence,
        safe_to_delete=safe,
        blockers=blockers,
    )


# --- Phase-2 / Phase-3 ports (design-only; do not invent safe_to_delete) ---

StringNameSearchFn = Callable[[str, str], Sequence[str]]


def string_name_reference_port(
    symbol_name: str,
    file_path: str,
    *,
    search: StringNameSearchFn | None = None,
) -> list[str]:
    """Textual name soft-blocker (SCARF BigGrep lesson).

    When ``search`` is None the port is inert. Callers should pass
    ``graph_corpus_string_name_hits`` (or a disk search) so hits outside the
    defining file yield blocker ``string_name_reference``.
    """
    if search is None:
        return []
    hits = list(search(symbol_name, file_path) or [])
    return ["string_name_reference"] if hits else []


def coverage_confirmation_port(
    symbol_id: str,
    *,
    coverage_hits: dict[str, int] | None = None,
) -> list[Evidence]:
    """Optional coverage / runtime confirmation.

    Zero hits add evidence only (never alone raises ``safe_to_delete``).
    Positive hits are applied by callers as ``coverage_runtime_use`` blockers.
    """
    if not coverage_hits:
        return []
    hits = int(coverage_hits.get(symbol_id, -1))
    if hits == 0:
        return [Evidence("coverage_zero_hits")]
    if hits > 0:
        return [Evidence("coverage_has_hits", f"hits={hits}")]
    return []


def local_advisory_triage_judge(finding: dict[str, Any]) -> dict[str, Any]:
    """Local (non-LLM) advisory triage for ``triage=true`` — never raises safe_to_delete."""
    blockers = [str(b) for b in (finding.get("blockers") or [])]
    if "tsoc_defer" in blockers:
        return {"verdict": "keep", "reason": "tsoc_defer_stopgap", "engine": "local_rules"}
    if "coverage_runtime_use" in blockers:
        return {"verdict": "keep", "reason": "runtime_coverage", "engine": "local_rules"}
    if finding.get("test_only"):
        return {
            "verdict": "delete_with_exclusive_tests",
            "reason": "test_only",
            "engine": "local_rules",
        }
    if "weak_or_ambiguous_call_edge" in blockers:
        return {
            "verdict": "investigate_call_sites",
            "reason": "ambiguous_call",
            "engine": "local_rules",
        }
    if "string_name_reference" in blockers:
        return {
            "verdict": "check_string_registries",
            "reason": "string_name_reference",
            "engine": "local_rules",
        }
    if "flag_controlled_dead_needs_refactor" in blockers:
        return {
            "verdict": "piranha_style_refactor",
            "reason": "flag_controlled_dead",
            "engine": "local_rules",
        }
    return {"verdict": "human_review", "reason": "uncertain", "engine": "local_rules"}


def llm_triage_port(
    finding: dict[str, Any],
    *,
    enabled: bool = False,
    judge: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """On-demand triage (local rules or injected LLM judge).

    Must not raise ``safe_to_delete``. Local/gateway only — honor
    no-cloud-exfiltration.
    """
    if not enabled:
        return None
    active_judge = judge or local_advisory_triage_judge
    verdict = dict(active_judge(finding) or {})
    verdict["safe_to_delete"] = False
    if finding.get("safe_to_delete"):
        # Preserve graph-proven safe deletes; triage is advisory for uncertain rows.
        verdict["safe_to_delete"] = True
        verdict["note"] = "graph_proof_retained"
    else:
        verdict.setdefault("note", "triage_cannot_raise_safe_to_delete")
        verdict["safe_to_delete"] = False
    return verdict


def flag_controlled_dead_port(
    *,
    flag_states: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Piranha-style stale feature-flag dead branches.

    Returns finding stubs only when flag state data is supplied.
    """
    if not flag_states:
        return []
    findings: list[dict[str, Any]] = []
    for key, state in flag_states.items():
        if not isinstance(state, dict):
            continue
        if state.get("constant_for_days", 0) < 90:
            continue
        findings.append(
            {
                "finding_kind": "flag_controlled_dead",
                "flag_key": key,
                "symbol": str(state.get("symbol") or key),
                "symbol_id": str(state.get("symbol_id") or ""),
                "path": str(state.get("path") or ""),
                "score": 0.60,
                "confidence": "medium",
                "safe_to_delete": False,
                "test_only": False,
                "evidence": [Evidence("flag_constant", str(state)).to_dict()],
                "blockers": ["flag_controlled_dead_needs_refactor"],
            }
        )
    return findings


_DISK_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".astloom",
    }
)
_DISK_SUFFIXES = frozenset(
    {
        ".py",
        ".pyi",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".go",
        ".java",
        ".kt",
        ".rs",
        ".yml",
        ".yaml",
        ".json",
        ".toml",
        ".md",
    }
)


def disk_string_name_hits(
    repo_root: str | Path | None,
    symbol_name: str,
    file_path: str,
    *,
    max_files: int = 200,
    max_hits: int = 5,
) -> list[str]:
    """Optional disk BigGrep-lite: quoted name outside the defining file.

    Bounded walk (skip VCS/venv/node_modules). Returns relative paths of hits.
    """
    if not repo_root:
        return []
    name = (symbol_name or "").strip()
    if len(name) < 2:
        return []
    root = Path(repo_root)
    if not root.is_dir():
        return []
    defining = (file_path or "").replace("\\", "/").lstrip("./")
    needles = (f"'{name}'", f'"{name}"', f"`{name}`")
    hits: list[str] = []
    scanned = 0
    for path in root.rglob("*"):
        if scanned >= max_files:
            break
        if not path.is_file():
            continue
        if any(part in _DISK_SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in _DISK_SUFFIXES:
            continue
        scanned += 1
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if rel == defining:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(n in text for n in needles):
            hits.append(rel)
            if len(hits) >= max_hits:
                break
    return hits


def days_since_touch_from_symbol(
    symbol: Any,
    *,
    repo_root: str | None = None,
) -> int | None:
    """File-edit age in days for recent_file_cap (not graph ingest updated_at).

    Prefer explicit metadata, then filesystem mtime under ``repo_root``.
    Never use ``symbol.updated_at`` — that is CKG ingest time and falsely
    triggers recent_file_cap after every sync.
    """
    meta = getattr(symbol, "metadata", None) or {}
    if isinstance(meta, dict) and meta.get("days_since_touch") is not None:
        try:
            return int(meta["days_since_touch"])
        except (TypeError, ValueError):
            pass
    raw = meta.get("mtime") if isinstance(meta, dict) else None
    if raw is None and repo_root:
        rel = (getattr(symbol, "file_path", "") or "").replace("\\", "/").lstrip("/")
        if rel:
            try:
                raw = Path(repo_root, rel).stat().st_mtime
            except OSError:
                raw = None
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)):
            ts = float(raw)
            # Heuristic: ms vs seconds
            if ts > 1e12:
                ts = ts / 1000.0
            touched = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            text = str(raw).strip().replace("Z", "+00:00")
            touched = datetime.fromisoformat(text)
            if touched.tzinfo is None:
                touched = touched.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - touched
        return max(0, int(delta.total_seconds() // 86400))
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def collect_directory_dynamic_taint(
    symbols: Iterable[Any],
    file_path: str,
    *,
    tainted_parents: set[str] | None = None,
) -> bool:
    """True when any symbol body in the same directory looks like a dynamic loader."""
    path = (file_path or "").replace("\\", "/")
    parent = path.rsplit("/", 1)[0] if "/" in path else ""
    if tainted_parents is not None:
        return parent in tainted_parents
    for sym in symbols:
        other = (getattr(sym, "file_path", "") or "").replace("\\", "/")
        other_parent = other.rsplit("/", 1)[0] if "/" in other else ""
        if other_parent != parent:
            continue
        blob = f"{getattr(sym, 'signature', '')}\n{getattr(sym, 'body', '')[:800]}"
        if blob_has_dynamic_loader(blob):
            return True
    return False
