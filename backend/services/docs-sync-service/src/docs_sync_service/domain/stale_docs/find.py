"""
Role: Orchestrate stale-documentation candidates from docs-sync store inputs.
Source of truth: docs/07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md
Allowed: task-scoped and opt-in project_scan (+ path_prefix); scores + evidence; act flags.
Forbidden: mutating Markdown; Memory as candidate SoT; inventing DOCUMENTED_BY.
"""

from __future__ import annotations

from typing import Any, Iterable

from ...models import CodeSymbol, DocAnchor, Document
from .scoring import ScoreInput, days_since_doc_touch, score_candidate

SCOPE_MODES = frozenset(
    {"task_neighborhood", "changed_symbols", "explicit_paths", "project_scan"}
)

_INDEX_NAMES = frozenset({"00-index.md", "readme.md"})
_RUNBOOK_HINTS = ("runbook", "connect", "operator")
_FIXTURE_MARKERS = ("never_linked", "ghost_", "never_should_exist")
_WIKI_TAGS = frozenset({"wiki", "repository-code-wiki", "code-wiki"})
_RELATION_KEYS = ("depends_on", "supersedes", "superseded_by", "complements")


def normalize_path_prefix(path_prefix: str | None) -> str | None:
    raw = (path_prefix or "").strip().replace("\\", "/")
    if not raw:
        return None
    return raw.rstrip("/")


def path_matches_prefix(file_path: str, prefix: str) -> bool:
    path = (file_path or "").replace("\\", "/")
    return path == prefix or path.startswith(prefix + "/")


def _is_index_doc(path: str) -> bool:
    name = (path or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name in _INDEX_NAMES


def _is_runbookish(path: str, tags: Iterable[str] | None = None) -> bool:
    blob = f"{path} {' '.join(tags or [])}".lower()
    return any(h in blob for h in _RUNBOOK_HINTS)


def _is_fixture_noise_path(path: str) -> bool:
    return any(m in (path or "") for m in _FIXTURE_MARKERS)


def _is_wiki_doc(path: str, tags: Iterable[str] | None, doc: Document) -> bool:
    """Published repository wiki page heuristics (doc 78 wiki_orphan)."""
    p = f"/{(path or '').replace('\\', '/').lstrip('/')}".lower()
    if "/wiki/" in p or p.startswith("/wiki"):
        return True
    tag_set = {str(t).strip().lower() for t in (tags or []) if str(t).strip()}
    if tag_set & _WIKI_TAGS:
        return True
    fm = doc.frontmatter if isinstance(doc.frontmatter, dict) else {}
    if str(fm.get("wiki_page_id") or fm.get("module_key") or "").strip():
        return True
    return False


def _doc_identity(doc: Document) -> str:
    return _fm_str(doc, "doc_id") or doc.id


def _declares_relation(doc: Document, other: Document) -> bool:
    """True when frontmatter already splits / depends on the peer (not a duplicate)."""
    other_id = _doc_identity(other)
    other_path = (other.path or "").replace("\\", "/")
    related = _fm_list(doc, "related_docs")
    for r in related:
        rr = r.replace("\\", "/")
        if rr == other_id or other_id in rr or rr == other_path or other_path.endswith(rr) or rr.endswith(other_path):
            return True
    fm = doc.frontmatter if isinstance(doc.frontmatter, dict) else {}
    for rel in fm.get("relations_declared") or []:
        if not isinstance(rel, dict):
            continue
        target = str(rel.get("target") or "").strip()
        if target and (target == other_id or other_id in target or other_path in target):
            return True
    for key in _RELATION_KEYS:
        val = _fm_str(doc, key)
        if val and (val == other_id or other_id in val):
            return True
    return False


def _topic_keys(doc: Document, link_tokens: list[str], resolved: list[CodeSymbol]) -> set[str]:
    """Shared SoT topic tokens for duplicate_authority clustering."""
    keys: set[str] = set()
    for sym in resolved:
        sp = (sym.symbol_path or "").strip()
        if sp:
            keys.add(f"sym:{sp}")
    for tok in link_tokens:
        t = (tok or "").strip()
        if t:
            keys.add(f"link:{t}")
    for pe in _fm_list(doc, "primary_entities"):
        keys.add(f"entity:{pe.lower()}")
    return keys


def _fm_str(doc: Document, key: str, default: str = "") -> str:
    fm = doc.frontmatter if isinstance(doc.frontmatter, dict) else {}
    return str(fm.get(key) or default).strip()


def _fm_list(doc: Document, key: str) -> list[str]:
    fm = doc.frontmatter if isinstance(doc.frontmatter, dict) else {}
    raw = fm.get(key)
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def _symbol_match_keys(sym: CodeSymbol) -> set[str]:
    """Match keys for Full-tier tokens: id, dotted path, and path::suffix forms."""
    fp = (sym.file_path or "").replace("\\", "/")
    sp = (sym.symbol_path or "").strip()
    keys: set[str] = {sym.id}
    if sp:
        keys.add(sp)
        parts = sp.split(".")
        for i in range(len(parts)):
            suffix = ".".join(parts[i:])
            if not suffix:
                continue
            keys.add(suffix)
            if fp:
                keys.add(f"{fp}::{suffix}")
    return {k.replace("\\", "/") for k in keys if k}


def _normalized_link_tokens(doc: Document) -> list[str]:
    raw = [*doc.linked_symbols, *_fm_list(doc, "linked_symbols")]
    out: list[str] = []
    seen: set[str] = set()
    for tok in raw:
        t = (tok or "").strip().replace("\\", "/")
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _is_path_ref(token: str) -> bool:
    """True for file/dir evidence links (common in Full-tier linked_symbols)."""
    t = (token or "").strip().replace("\\", "/")
    if not t or "::" in t:
        return False
    if "/" in t:
        return True
    return t.endswith((".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"))


def _resolve_path_ref(token: str, symbols: list[CodeSymbol]) -> CodeSymbol | None:
    t = (token or "").strip().replace("\\", "/").rstrip("/")
    if not t:
        return None
    for sym in symbols:
        fp = (sym.file_path or "").replace("\\", "/")
        if not fp:
            continue
        if fp == t or fp.startswith(t + "/") or t.endswith(fp) or fp.endswith("/" + t.rsplit("/", 1)[-1]) and t.endswith(fp):
            return sym
    return None


def _resolve_link(
    token: str,
    by_key: dict[str, CodeSymbol],
    symbols: list[CodeSymbol],
) -> CodeSymbol | None:
    t = (token or "").strip().replace("\\", "/")
    if not t:
        return None
    if t in by_key:
        return by_key[t]
    # suffix match on symbol_path / keyed forms
    for key, sym in by_key.items():
        if key.endswith(t) or t.endswith(sym.symbol_path):
            return sym
    if _is_path_ref(t):
        return _resolve_path_ref(t, symbols)
    return None


def _append_row(
    row: dict[str, Any],
    *,
    min_confidence: float,
    include_uncertain: bool,
    candidates: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
) -> None:
    if float(row.get("score") or 0) < min_confidence:
        return
    act = bool(row.get("safe_to_delete") or row.get("safe_to_unlink") or row.get("safe_to_update"))
    if act and not row.get("blockers"):
        candidates.append(row)
    elif include_uncertain or row.get("blockers"):
        skipped.append(row)
    elif include_uncertain:
        skipped.append(row)


def find_stale_doc_candidates(
    documents: list[Document],
    symbols: list[CodeSymbol],
    anchors: list[DocAnchor],
    *,
    scope_mode: str,
    anchor_symbols: list[str] | None = None,
    anchor_paths: list[str] | None = None,
    max_results: int = 50,
    include_uncertain: bool = False,
    freshness: str = "ok",
    min_confidence: float | None = None,
    path_prefix: str | None = None,
    include_coverage_gaps: bool = False,
) -> dict[str, Any]:
    """Return stale-documentation candidate payload for MCP / service callers."""
    mode = (scope_mode or "").strip()
    if mode not in SCOPE_MODES:
        raise ValueError(
            "scope_mode must be one of: task_neighborhood, changed_symbols, "
            "explicit_paths, project_scan"
        )
    max_results = max(1, min(int(max_results or 50), 200))
    if min_confidence is None:
        min_confidence = 0.50 if mode == "project_scan" else 0.0
    else:
        try:
            min_confidence = float(min_confidence)
        except (TypeError, ValueError):
            min_confidence = 0.50 if mode == "project_scan" else 0.0
    min_confidence = max(0.0, min(1.0, min_confidence))
    prefix = normalize_path_prefix(path_prefix)

    by_id = {s.id: s for s in symbols}
    by_key: dict[str, CodeSymbol] = {}
    for sym in symbols:
        for key in _symbol_match_keys(sym):
            by_key[key] = sym

    anchors_by_doc: dict[str, list[DocAnchor]] = {}
    anchors_by_symbol: dict[str, list[DocAnchor]] = {}
    for anc in anchors:
        anchors_by_doc.setdefault(anc.doc_id, []).append(anc)
        anchors_by_symbol.setdefault(anc.symbol_id, []).append(anc)

    wanted_names = {s.strip() for s in (anchor_symbols or []) if str(s).strip()}
    wanted_paths = {
        p.strip().replace("\\", "/") for p in (anchor_paths or []) if str(p).strip()
    }

    def doc_in_scope(doc: Document) -> bool:
        path = (doc.path or "").replace("\\", "/")
        if prefix and not path_matches_prefix(path, prefix):
            return False
        if mode == "project_scan":
            return True
        if mode == "explicit_paths":
            return any(
                path == wp or path.startswith(wp.rstrip("/") + "/") or wp in path
                for wp in wanted_paths
            )
        # task_neighborhood / changed_symbols: docs linked to anchors
        if not wanted_names and not wanted_paths:
            return False
        for tok in _normalized_link_tokens(doc):
            sym = _resolve_link(tok, by_key, symbols)
            if sym is None:
                continue
            if sym.id in wanted_names or sym.symbol_path in wanted_names or sym.symbol_path.split(".")[-1] in wanted_names:
                return True
            sp = (sym.file_path or "").replace("\\", "/")
            if any(sp == wp or sp.startswith(wp.rstrip("/") + "/") or wp in sp for wp in wanted_paths):
                return True
        for anc in anchors_by_doc.get(doc.id, []):
            sym = by_id.get(anc.symbol_id)
            if sym is None:
                continue
            if sym.id in wanted_names or sym.symbol_path in wanted_names:
                return True
            sp = (sym.file_path or "").replace("\\", "/")
            if any(sp == wp or sp.startswith(wp.rstrip("/") + "/") for wp in wanted_paths):
                return True
        # path-only anchors on the doc itself
        if any(path == wp or path.startswith(wp.rstrip("/") + "/") or wp in path for wp in wanted_paths):
            return True
        return False

    if mode != "project_scan" and not wanted_names and not wanted_paths:
        empty: dict[str, Any] = {
            "freshness": freshness,
            "scope_mode": mode,
            "candidates": [],
            "skipped_uncertain": [],
            "kpi_hints": {
                "stale_docs_candidates_surfaced": 0,
                "stale_docs_candidates_skipped_uncertain": 0,
                "stale_docs_candidates_resolved": 0,
            },
            "note": "no_anchor_symbols_or_paths",
        }
        if prefix:
            empty["path_prefix"] = prefix
        return empty

    pool = [d for d in documents if doc_in_scope(d)]
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    emitted_ids: set[str] = set()

    for doc in pool:
        path = (doc.path or "").replace("\\", "/")
        if _is_index_doc(path) or _is_fixture_noise_path(path):
            continue
        tags = _fm_list(doc, "tags")
        blockers: list[str] = []
        if _is_runbookish(path, tags):
            blockers.append("runbook_or_ops_doc")
        decision_refs = list(doc.decision_refs) + _fm_list(doc, "decision_refs")
        if decision_refs:
            blockers.append("open_decision_refs")
        if _fm_str(doc, "supersedes") or _fm_str(doc, "superseded_by"):
            # soft: still referenced supersession metadata
            blockers.append("supersedes_chain")

        authority = _fm_str(doc, "authority")
        lifecycle = _fm_str(doc, "lifecycle_lane")
        doc_anchors = anchors_by_doc.get(doc.id, [])
        no_documented_by = not doc_anchors

        link_tokens = _normalized_link_tokens(doc)
        resolved: list[CodeSymbol] = []
        missing_symbol_refs: list[str] = []
        unresolved_path_refs: list[str] = []
        for tok in link_tokens:
            sym = _resolve_link(tok, by_key, symbols)
            if sym is not None:
                resolved.append(sym)
            elif _is_path_ref(tok):
                # Path/dir evidence without a docs-sync symbol under that path —
                # often sparse index, not a true ghost symbol reference.
                unresolved_path_refs.append(tok)
            else:
                missing_symbol_refs.append(tok)

        stale_anchor_hits: list[DocAnchor] = []
        for anc in doc_anchors:
            sym = by_id.get(anc.symbol_id)
            if sym is None:
                sid = (anc.symbol_id or "").strip()
                if sid:
                    missing_symbol_refs.append(sid)
                continue
            if anc.recorded_hash != sym.body_hash:
                stale_anchor_hits.append(anc)

        missing_tokens = missing_symbol_refs
        all_links_missing = bool(link_tokens) and not resolved and not doc_anchors and (
            bool(missing_symbol_refs) or (bool(unresolved_path_refs) and not missing_symbol_refs)
        )
        # Ghost only from missing symbol refs (path::Name / dotted paths), not path-only FM links.
        ghost_majority = bool(link_tokens) and bool(missing_symbol_refs) and (
            len(missing_symbol_refs) * 2 >= max(1, len([t for t in link_tokens if not _is_path_ref(t)]))
        )
        wiki_doc = _is_wiki_doc(path, tags, doc)
        normative_current = authority.lower() == "normative" and lifecycle.lower() in {
            "current",
            "transition",
            "",
        }

        finding_kind = ""
        if lifecycle == "historical" or (doc.state.value if hasattr(doc.state, "value") else str(doc.state)) in {
            "archived",
            "stale",
        }:
            finding_kind = "superseded_retrieval_risk"
        elif wiki_doc and no_documented_by and not resolved and not missing_symbol_refs:
            finding_kind = "wiki_orphan"
        elif stale_anchor_hits and not missing_symbol_refs:
            finding_kind = "stale_anchor"
        elif missing_symbol_refs and (ghost_majority or not resolved):
            finding_kind = "ghost_link"
        elif no_documented_by and not link_tokens:
            # Normative current standards with empty linked_symbols are linking-debt,
            # not delete orphans (quality-audit linking_gap owns that signal).
            # Future/historical lanes are intentional backlog or archive — not orphans.
            if normative_current or lifecycle.lower() in {"future", "historical"}:
                finding_kind = ""
            else:
                concern = _fm_str(doc, "concern_lane")
                if concern in {"product", "design", "contract", "standard"} or authority:
                    finding_kind = "orphan_doc"
        elif no_documented_by and all_links_missing and missing_symbol_refs:
            finding_kind = "orphan_doc"
        elif no_documented_by and all_links_missing and unresolved_path_refs and not missing_symbol_refs:
            # Path-only linked_symbols with no docs-sync symbols under those paths:
            # incomplete docs-symbol index — do not treat as orphan/ghost delete debt.
            finding_kind = ""
        elif missing_symbol_refs:
            finding_kind = "ghost_link"

        if not finding_kind:
            continue

        days = days_since_doc_touch(updated_at=doc.updated_at, frontmatter=doc.frontmatter)
        scored = score_candidate(
            ScoreInput(
                finding_kind=finding_kind,
                authority=authority,
                lifecycle_lane=lifecycle,
                blockers=blockers,
                freshness=freshness,
                days_since_touch=days,
                all_links_missing=(no_documented_by and not link_tokens)
                or (bool(missing_symbol_refs) and not resolved and no_documented_by),
                ghost_majority=ghost_majority,
                has_stale_anchors=bool(stale_anchor_hits),
                no_documented_by=no_documented_by,
            )
        )
        evidence = [e.to_dict() for e in scored.evidence]
        for tok in missing_symbol_refs[:5]:
            evidence.append({"kind": "linked_symbol_missing", "detail": tok})
        for tok in unresolved_path_refs[:3]:
            evidence.append({"kind": "path_link_unresolved", "detail": tok})
        for anc in stale_anchor_hits[:3]:
            evidence.append(
                {
                    "kind": "anchor_hash_mismatch",
                    "detail": f"{anc.symbol_id}:{anc.recorded_hash}",
                }
            )

        row = {
            "doc_id": _doc_identity(doc),
            "path": path,
            "finding_kind": finding_kind,
            "score": scored.score,
            "confidence": scored.tier,
            "evidence": evidence,
            "blockers": list(dict.fromkeys([*blockers, *scored.blockers])),
            "safe_to_delete": bool(scored.safe_to_delete) and not blockers,
            "safe_to_unlink": bool(scored.safe_to_unlink),
            "safe_to_update": bool(scored.safe_to_update),
            "title": doc.title,
        }
        # Any remaining hard freshness/runbook blockers demote delete.
        if row["blockers"]:
            row["safe_to_delete"] = False
        _append_row(
            row,
            min_confidence=min_confidence,
            include_uncertain=include_uncertain,
            candidates=candidates,
            skipped=skipped,
        )
        emitted_ids.add(doc.id)

    # duplicate_authority: normative+current peers sharing SoT topics without declared relation.
    topic_docs: dict[str, list[Document]] = {}
    for doc in pool:
        if doc.id in emitted_ids:
            continue
        path = (doc.path or "").replace("\\", "/")
        if _is_index_doc(path) or _is_fixture_noise_path(path):
            continue
        authority = _fm_str(doc, "authority").lower()
        lifecycle = _fm_str(doc, "lifecycle_lane").lower() or "current"
        if authority != "normative" or lifecycle != "current":
            continue
        link_tokens = _normalized_link_tokens(doc)
        resolved: list[CodeSymbol] = []
        for tok in link_tokens:
            sym = _resolve_link(tok, by_key, symbols)
            if sym is not None:
                resolved.append(sym)
        topics = _topic_keys(doc, link_tokens, resolved)
        if not topics:
            continue
        for topic in topics:
            topic_docs.setdefault(topic, []).append(doc)

    duplicate_peers: dict[str, set[str]] = {}
    for _topic, docs_for_topic in topic_docs.items():
        if len(docs_for_topic) < 2:
            continue
        for i, left in enumerate(docs_for_topic):
            for right in docs_for_topic[i + 1 :]:
                if _declares_relation(left, right) or _declares_relation(right, left):
                    continue
                duplicate_peers.setdefault(left.id, set()).add(_doc_identity(right))
                duplicate_peers.setdefault(right.id, set()).add(_doc_identity(left))

    for doc in pool:
        peers = duplicate_peers.get(doc.id)
        if not peers:
            continue
        path = (doc.path or "").replace("\\", "/")
        tags = _fm_list(doc, "tags")
        blockers: list[str] = []
        if _is_runbookish(path, tags):
            blockers.append("runbook_or_ops_doc")
        decision_refs = list(doc.decision_refs) + _fm_list(doc, "decision_refs")
        if decision_refs:
            blockers.append("open_decision_refs")
        authority = _fm_str(doc, "authority")
        lifecycle = _fm_str(doc, "lifecycle_lane")
        days = days_since_doc_touch(updated_at=doc.updated_at, frontmatter=doc.frontmatter)
        scored = score_candidate(
            ScoreInput(
                finding_kind="duplicate_authority",
                authority=authority,
                lifecycle_lane=lifecycle,
                blockers=blockers,
                freshness=freshness,
                days_since_touch=days,
                no_documented_by=not anchors_by_doc.get(doc.id),
            )
        )
        evidence = [e.to_dict() for e in scored.evidence]
        for peer in sorted(peers)[:5]:
            evidence.append({"kind": "duplicate_peer", "detail": peer})
        row = {
            "doc_id": _doc_identity(doc),
            "path": path,
            "finding_kind": "duplicate_authority",
            "score": scored.score,
            "confidence": scored.tier,
            "evidence": evidence,
            "blockers": list(dict.fromkeys([*blockers, *scored.blockers])),
            "safe_to_delete": False,
            "safe_to_unlink": False,
            "safe_to_update": bool(scored.safe_to_update),
            "title": doc.title,
            "duplicate_peers": sorted(peers),
        }
        _append_row(
            row,
            min_confidence=min_confidence,
            include_uncertain=include_uncertain,
            candidates=candidates,
            skipped=skipped,
        )
        emitted_ids.add(doc.id)

    if include_coverage_gaps:
        for sym in symbols:
            if not sym.doc_required:
                continue
            if anchors_by_symbol.get(sym.id):
                continue
            if _is_fixture_noise_path(f"{sym.symbol_path} {sym.file_path}"):
                continue
            if mode != "project_scan":
                if wanted_names and not (
                    sym.id in wanted_names
                    or sym.symbol_path in wanted_names
                    or sym.symbol_path.split(".")[-1] in wanted_names
                ):
                    sp = (sym.file_path or "").replace("\\", "/")
                    if not any(sp == wp or sp.startswith(wp.rstrip("/") + "/") for wp in wanted_paths):
                        continue
            scored = score_candidate(
                ScoreInput(
                    finding_kind="coverage_gap",
                    freshness=freshness,
                    no_documented_by=True,
                )
            )
            row = {
                "doc_id": None,
                "path": (sym.file_path or "").replace("\\", "/"),
                "symbol": sym.symbol_path,
                "symbol_id": sym.id,
                "finding_kind": "coverage_gap",
                "score": scored.score,
                "confidence": scored.tier,
                "evidence": [e.to_dict() for e in scored.evidence],
                "blockers": list(scored.blockers),
                "safe_to_delete": False,
                "safe_to_unlink": False,
                "safe_to_update": False,
            }
            _append_row(
                row,
                min_confidence=min_confidence,
                include_uncertain=include_uncertain,
                candidates=candidates,
                skipped=skipped,
            )

    candidates.sort(key=lambda r: (-float(r.get("score") or 0), str(r.get("path") or "")))
    skipped.sort(key=lambda r: (-float(r.get("score") or 0), str(r.get("path") or "")))
    surfaced = candidates[:max_results]
    uncertain = skipped[:max_results]
    out: dict[str, Any] = {
        "freshness": freshness,
        "scope_mode": mode,
        "candidates": surfaced,
        "skipped_uncertain": uncertain,
        "kpi_hints": {
            "stale_docs_candidates_surfaced": len(surfaced),
            "stale_docs_candidates_skipped_uncertain": len(uncertain),
            "stale_docs_candidates_resolved": 0,
        },
    }
    if prefix:
        out["path_prefix"] = prefix
    return out
