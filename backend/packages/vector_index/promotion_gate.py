"""Promotion gate: recall@k / latency / RAM proxy vs dense baseline (ADR 08).

Role: in-repo operator acceptance for enabling turbovec in a profile.
SoT: synthetic or caller-provided float32 corpus; never mutates production SoR.
Allowed: compare InMemoryVectorIndex or TurboVecIndexAdapter to brute-force top-k.
Forbidden: treating this report as a substitute for ACL / tenant isolation tests.
"""

from __future__ import annotations

import argparse
import json
import resource
import time
from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np
from numpy.typing import NDArray

from .in_memory import InMemoryVectorIndex
from .turbovec_adapter import TurboVecIndexAdapter, turbovec_importable


@dataclass(frozen=True)
class PromotionGateResult:
    """Machine-readable promotion evidence for one corpus + bit_width."""

    corpus_size: int
    dim: int
    k: int
    bit_width: int
    recall_at_k: float
    baseline_latency_ms: float
    accelerator_latency_ms: float
    baseline_rss_bytes: int
    accelerator_rss_bytes: int
    accelerator: str
    recall_delta_max: float
    passed: bool
    reason: str

    def public(self) -> dict[str, Any]:
        return asdict(self)


def _rss_bytes() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # ru_maxrss is KB on Linux, bytes on macOS — normalize via heuristic.
    raw = int(usage.ru_maxrss)
    return raw * 1024 if raw < 10**9 else raw


def _normalize_rows(matrix: NDArray[np.float32]) -> NDArray[np.float32]:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return matrix / norms


def brute_force_topk(
    query: NDArray[np.float32],
    corpus: NDArray[np.float32],
    ids: Sequence[int],
    k: int,
) -> list[int]:
    scores = corpus @ query
    order = np.argsort(-scores)[:k]
    return [int(ids[i]) for i in order.tolist()]


def recall_at_k(baseline: Sequence[int], candidate: Sequence[int], k: int) -> float:
    if k <= 0:
        return 0.0
    base = set(int(x) for x in baseline[:k])
    if not base:
        return 1.0
    hit = sum(1 for x in candidate[:k] if int(x) in base)
    return hit / float(len(base))


def build_synthetic_corpus(
    *,
    n: int = 256,
    dim: int = 64,
    seed: int = 7,
) -> tuple[NDArray[np.float32], list[int], NDArray[np.float32]]:
    rng = np.random.default_rng(seed)
    corpus = _normalize_rows(rng.standard_normal((n, dim), dtype=np.float32))
    ids = list(range(1, n + 1))
    query = _normalize_rows(rng.standard_normal((1, dim), dtype=np.float32))[0]
    return corpus, ids, query


def run_promotion_gate(
    *,
    n: int = 256,
    dim: int = 64,
    k: int = 10,
    bit_width: int = 4,
    seed: int = 7,
    recall_delta_max: float = 0.05,
    prefer_turbovec: bool = True,
) -> PromotionGateResult:
    """Compare accelerator allowlist search to brute-force cosine top-k."""
    if dim <= 0 or dim % 8 != 0:
        raise ValueError("dim must be a positive multiple of 8")
    corpus, ids, query = build_synthetic_corpus(n=n, dim=dim, seed=seed)
    allow = list(ids)

    t0 = time.perf_counter()
    baseline_ids = brute_force_topk(query, corpus, ids, k)
    baseline_latency_ms = (time.perf_counter() - t0) * 1000.0
    baseline_rss = _rss_bytes()

    accelerator_name = "in_memory"
    adapter: Any
    if prefer_turbovec and turbovec_importable():
        created = TurboVecIndexAdapter.try_create(dim=dim, bit_width=bit_width)
        if created is not None:
            adapter = created
            accelerator_name = "turbovec"
        else:
            adapter = InMemoryVectorIndex(dim=dim)
    else:
        adapter = InMemoryVectorIndex(dim=dim)

    adapter.upsert(ids, corpus)
    t1 = time.perf_counter()
    _scores, hit_ids = adapter.search(query, k=k, allowlist=allow)
    accelerator_latency_ms = (time.perf_counter() - t1) * 1000.0
    accelerator_rss = _rss_bytes()
    candidate_ids = [int(x) for x in np.asarray(hit_ids).tolist()]
    recall = recall_at_k(baseline_ids, candidate_ids, k)
    passed = recall + 1e-9 >= (1.0 - recall_delta_max)
    reason = (
        "ok"
        if passed
        else f"recall_at_{k}={recall:.4f} below floor {1.0 - recall_delta_max:.4f}"
    )
    return PromotionGateResult(
        corpus_size=n,
        dim=dim,
        k=k,
        bit_width=bit_width,
        recall_at_k=float(recall),
        baseline_latency_ms=float(baseline_latency_ms),
        accelerator_latency_ms=float(accelerator_latency_ms),
        baseline_rss_bytes=int(baseline_rss),
        accelerator_rss_bytes=int(accelerator_rss),
        accelerator=accelerator_name,
        recall_delta_max=float(recall_delta_max),
        passed=passed,
        reason=reason,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TurboVec vs dense baseline promotion gate")
    parser.add_argument("--n", type=int, default=256)
    parser.add_argument("--dim", type=int, default=64)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--bit-width", type=int, default=4)
    parser.add_argument("--recall-delta-max", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    result = run_promotion_gate(
        n=args.n,
        dim=args.dim,
        k=args.k,
        bit_width=args.bit_width,
        seed=args.seed,
        recall_delta_max=args.recall_delta_max,
    )
    print(json.dumps(result.public(), indent=2, sort_keys=True))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
