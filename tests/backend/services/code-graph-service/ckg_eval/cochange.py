"""Git co-change pair extraction and set metrics (independent of graph SoR)."""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=True,
        stderr=subprocess.DEVNULL,
    )


def cochange_pairs_from_commits(
    repo: Path,
    *,
    min_support: int = 2,
    max_commits: int = 200,
) -> dict[tuple[str, str], int]:
    """Return undirected file-pair → co-commit count from git history.

    Labels are derived only from ``git log`` — never from graph edges.
    """
    repo = Path(repo)
    log = _git(
        repo,
        "log",
        f"-n{max_commits}",
        "--name-only",
        "--pretty=format:COMMIT",
        "--",
        ".",
    )
    counts: Counter[tuple[str, str]] = Counter()
    batch: list[str] = []
    for line in log.splitlines():
        line = line.strip().replace("\\", "/")
        if line == "COMMIT":
            _accumulate_pairs(batch, counts)
            batch = []
            continue
        if line and not line.startswith("COMMIT"):
            batch.append(line)
    _accumulate_pairs(batch, counts)
    return {pair: n for pair, n in counts.items() if n >= min_support}


def _accumulate_pairs(files: list[str], counts: Counter[tuple[str, str]]) -> None:
    uniq = sorted({f for f in files if f and not f.endswith("/")})
    for i, a in enumerate(uniq):
        for b in uniq[i + 1 :]:
            counts[(a, b)] += 1


def partners_for(file_path: str, pairs: dict[tuple[str, str], int]) -> set[str]:
    norm = file_path.replace("\\", "/")
    out: set[str] = set()
    for (a, b), _n in pairs.items():
        if a == norm:
            out.add(b)
        elif b == norm:
            out.add(a)
    return out


def precision_recall_f1(predicted: set[str], gold: set[str]) -> dict[str, float]:
    if not predicted and not gold:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not predicted:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    if not gold:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    tp = len(predicted & gold)
    precision = tp / len(predicted)
    recall = tp / len(gold)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }
