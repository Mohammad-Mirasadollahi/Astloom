"""Offline honesty eval for explore / change-risk / retrieval / communities.

Ground truth must come from git co-change or human labels — never from Neo4j
self-walk (ADR 19 circular-claim ban).
"""

from .cochange import cochange_pairs_from_commits, precision_recall_f1
from .metrics import average_ndcg, ndcg_at_k
from .reports import write_eval_report

__all__ = [
    "average_ndcg",
    "cochange_pairs_from_commits",
    "ndcg_at_k",
    "precision_recall_f1",
    "write_eval_report",
]
