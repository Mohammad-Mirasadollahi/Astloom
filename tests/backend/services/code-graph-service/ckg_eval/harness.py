"""Score explore / change-risk / communities / hybrid against independent labels."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from code_graph_service.core import CodeGraphService, Scope

from .cochange import cochange_pairs_from_commits, partners_for, precision_recall_f1
from .metrics import average_ndcg, ndcg_at_k
from .reports import write_eval_report


def files_from_explore(pack: dict[str, Any], *, exclude: set[str] | None = None) -> set[str]:
    skip = {p.replace("\\", "/") for p in (exclude or set())}
    out: set[str] = set()
    for sec in pack.get("sections") or []:
        sec_path = str(sec.get("file_path") or "").replace("\\", "/")
        if sec_path and sec_path not in skip and sec_path != "(unknown)":
            out.add(sec_path)
        for sym in sec.get("symbols") or []:
            fp = str(sym.get("file_path") or sec_path or "").replace("\\", "/")
            if fp and fp not in skip and fp != "(unknown)":
                out.add(fp)
    return out


def files_from_detect_changes(
    report: dict[str, Any],
    svc: CodeGraphService,
    scope: Scope,
    *,
    exclude: set[str] | None = None,
) -> set[str]:
    """Predict related files via affected flows and CALLS neighbors of changed symbols."""
    skip = {p.replace("\\", "/") for p in (exclude or set())}
    by_id = {s.id: s for s in svc.store.list_symbols(scope)}
    out: set[str] = set()
    changed_ids = {str(r.get("symbol_id") or "") for r in report.get("changed_functions") or []}
    for flow in report.get("affected_flows") or []:
        for sid in flow.get("path_ids") or []:
            sym = by_id.get(sid)
            if sym is None:
                continue
            fp = sym.file_path.replace("\\", "/")
            if fp and fp not in skip:
                out.add(fp)
    for edge in svc.store.list_edges(scope):
        if edge.rel_type not in {"CALLS", "ROUTES_TO"}:
            continue
        if edge.source_id in changed_ids or edge.target_id in changed_ids:
            for sid in (edge.source_id, edge.target_id):
                sym = by_id.get(sid)
                if sym is None:
                    continue
                fp = sym.file_path.replace("\\", "/")
                if fp and fp not in skip:
                    out.add(fp)
    return out


def score_explore_and_risk(
    svc: CodeGraphService,
    scope: Scope,
    git_repo: Path,
    *,
    seed_files: list[str],
    explore_queries: dict[str, str],
    min_support: int = 2,
) -> dict[str, Any]:
    pairs = cochange_pairs_from_commits(git_repo, min_support=min_support)
    per_seed: list[dict[str, Any]] = []
    explore_f1: list[float] = []
    risk_f1: list[float] = []
    for seed in seed_files:
        gold = partners_for(seed, pairs)
        query = explore_queries.get(seed) or Path(seed).stem
        pack = svc.explore(scope, query)
        pred_explore = files_from_explore(pack, exclude={seed})
        m_explore = precision_recall_f1(pred_explore, gold)
        explore_f1.append(m_explore["f1"])

        report = svc.detect_changes(scope, [seed])
        pred_risk = files_from_detect_changes(report, svc, scope, exclude={seed})
        m_risk = precision_recall_f1(pred_risk, gold)
        risk_f1.append(m_risk["f1"])

        per_seed.append(
            {
                "seed": seed,
                "gold_partners": sorted(gold),
                "explore": {"predicted": sorted(pred_explore), **m_explore},
                "change_risk": {"predicted": sorted(pred_risk), **m_risk},
                "risk_score": report.get("risk_score"),
            }
        )
    summary = {
        "label_source": "git_cochange",
        "pair_count": len(pairs),
        "seeds": per_seed,
        "mean_explore_f1": round(sum(explore_f1) / len(explore_f1), 4) if explore_f1 else 0.0,
        "mean_change_risk_f1": round(sum(risk_f1) / len(risk_f1), 4) if risk_f1 else 0.0,
    }
    write_eval_report("cochange-explore-risk", summary)
    return summary


def score_retrieval_ndcg(
    svc: CodeGraphService,
    scope: Scope,
    gold_queries: list[dict[str, Any]],
    *,
    k: int = 10,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Gold items are qualified_name strings resolved to symbol ids after ingest."""
    # Rank only callable/type symbols so doc projections do not dilute nDCG.
    usable = [
        s
        for s in svc.store.list_symbols(scope)
        if s.kind.value in {"function", "method", "class", "route"}
    ]
    by_qn = {s.qualified_name: s.id for s in usable}
    usable_ids = {s.id for s in usable}
    scores: list[float] = []
    rows: list[dict[str, Any]] = []
    for item in gold_queries:
        query = str(item["query"])
        relevant_qns = {str(x) for x in item.get("relevant_qualified_names") or []}
        relevant_ids = {by_qn[q] for q in relevant_qns if q in by_qn}
        hits = svc.hybrid_search(scope, query, top_k=k * 3).get("hits") or []
        ranked = [
            str(h.get("symbol_id") or "")
            for h in hits
            if str(h.get("symbol_id") or "") in usable_ids
        ][:k]
        score = ndcg_at_k(ranked, relevant_ids, k=k)
        scores.append(score)
        rows.append(
            {
                "query": query,
                "ndcg": score,
                "relevant_found": len(relevant_ids),
                "ranked_top": ranked[:5],
            }
        )
    mean = average_ndcg(scores)
    summary = {
        "label_source": "gold_queries",
        "k": k,
        "mean_ndcg": mean,
        "threshold": threshold,
        "passes_threshold": mean >= threshold,
        "queries": rows,
    }
    write_eval_report("retrieval-ndcg", summary)
    return summary


def score_community_vs_cochange(
    svc: CodeGraphService,
    scope: Scope,
    git_repo: Path,
    *,
    min_support: int = 2,
) -> dict[str, Any]:
    pairs = cochange_pairs_from_commits(git_repo, min_support=min_support)
    arch = svc.architecture_overview(scope)
    # Map file → community ids of its symbols
    file_communities: dict[str, set[str]] = {}
    member_to_community: dict[str, str] = {}
    for c in arch.get("communities") or []:
        cid = str(c.get("id"))
        for mid in c.get("members") or []:
            member_to_community[str(mid)] = cid
    for sym in svc.store.list_symbols(scope):
        cid = member_to_community.get(sym.id)
        if cid is None:
            continue
        fp = sym.file_path.replace("\\", "/")
        file_communities.setdefault(fp, set()).add(cid)

    same = 0
    total = 0
    for (a, b), _n in pairs.items():
        ca = file_communities.get(a)
        cb = file_communities.get(b)
        if not ca or not cb:
            continue
        total += 1
        if ca & cb:
            same += 1
    rate = round(same / total, 4) if total else 0.0
    summary = {
        "label_source": "git_cochange",
        "pair_count_scored": total,
        "same_community_pairs": same,
        "same_community_rate": rate,
        "algorithm": arch.get("algorithm"),
    }
    write_eval_report("community-vs-cochange", summary)
    return summary
