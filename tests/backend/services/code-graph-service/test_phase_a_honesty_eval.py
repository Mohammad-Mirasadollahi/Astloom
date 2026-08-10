"""Phase A honesty eval: co-change / nDCG / community (ADR 19 non-circular)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore

from ckg_eval.cochange import cochange_pairs_from_commits, precision_recall_f1
from ckg_eval.harness import score_community_vs_cochange, score_explore_and_risk, score_retrieval_ndcg
from ckg_eval.metrics import ndcg_at_k
from ckg_eval.reports import eval_artifact_root

AUTH_SRC = '''
from crypto import verify_password

def check_password(password):
    return len(password) > 8

def login(user, password, stored_hash="x"):
    if not check_password(password):
        return False
    return verify_password(password, stored_hash)
'''

API_SRC = '''
from fastapi import APIRouter
from auth import login as do_login

router = APIRouter()

@router.post("/login")
def login_route(user, password):
    return do_login(user, password)
'''

HASH_SRC = '''
def hash_password(value: str) -> str:
    return f"hashed:{value}"

def verify_password(value: str, hashed: str) -> bool:
    return hash_password(value) == hashed
'''

EVAL_DIR = Path(__file__).resolve().parent / "ckg_eval"


def _git(repo: Path, *args: str) -> None:
    subprocess.check_call(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _build_cochange_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "eval@astloom.test")
    _git(repo, "config", "user.name", "Eval")
    (repo / "src").mkdir()
    files = {
        "src/auth.py": AUTH_SRC,
        "src/api.py": API_SRC,
        "src/crypto.py": HASH_SRC,
    }
    for rel, body in files.items():
        (repo / rel).write_text(body, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    # Co-change auth+api repeatedly (gold partners)
    for i in range(3):
        (repo / "src/auth.py").write_text(AUTH_SRC + f"\n# touch {i}\n", encoding="utf-8")
        (repo / "src/api.py").write_text(API_SRC + f"\n# touch {i}\n", encoding="utf-8")
        _git(repo, "add", "src/auth.py", "src/api.py")
        _git(repo, "commit", "-m", f"auth-api-{i}")
    # Co-change crypto alone with itself via auth? keep crypto paired with auth lightly
    for i in range(2):
        (repo / "src/auth.py").write_text(AUTH_SRC + f"\n# crypto {i}\n", encoding="utf-8")
        (repo / "src/crypto.py").write_text(HASH_SRC + f"\n# crypto {i}\n", encoding="utf-8")
        _git(repo, "add", "src/auth.py", "src/crypto.py")
        _git(repo, "commit", "-m", f"auth-crypto-{i}")
    return repo


def _ingest_repo(svc: CodeGraphService, scope: Scope, repo: Path) -> None:
    for rel in ("src/auth.py", "src/api.py", "src/crypto.py"):
        body = (repo / rel).read_text(encoding="utf-8")
        svc.ingest_file(
            scope,
            "agent",
            f"c-{rel}",
            f"k-{rel}",
            {"file_path": rel, "source": body, "language": "python"},
        )


def test_cochange_pairs_independent_of_graph(tmp_path: Path):
    repo = _build_cochange_repo(tmp_path)
    pairs = cochange_pairs_from_commits(repo, min_support=2)
    assert ("src/api.py", "src/auth.py") in pairs or ("src/auth.py", "src/api.py") in pairs
    # Label source is git only — no store involved
    assert pairs


def test_ndcg_metric_unit():
    assert ndcg_at_k(["a", "b", "c"], {"a"}, k=3) == 1.0
    assert ndcg_at_k(["b", "a"], {"a"}, k=2) < 1.0
    assert precision_recall_f1({"a"}, {"a", "b"})["recall"] == 0.5


def test_phase_a_explore_risk_community_and_ndcg(tmp_path: Path):
    repo = _build_cochange_repo(tmp_path)
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("eval-t", "eval-w", "eval-p")
    _ingest_repo(svc, scope, repo)

    cochange = score_explore_and_risk(
        svc,
        scope,
        repo,
        seed_files=["src/auth.py"],
        explore_queries={"src/auth.py": "login password"},
        min_support=2,
    )
    assert "mean_explore_f1" in cochange
    assert "mean_change_risk_f1" in cochange
    assert cochange["label_source"] == "git_cochange"
    assert cochange["pair_count"] >= 1
    # Harness must surface at least one co-changed partner (not a hollow 0/0 report).
    assert cochange["mean_explore_f1"] > 0.0 or cochange["mean_change_risk_f1"] > 0.0
    assert any(cochange["seeds"][0]["explore"]["predicted"] or cochange["seeds"][0]["change_risk"]["predicted"])

    gold_path = EVAL_DIR / "fixtures" / "gold_queries.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    # Prefer function/method/class symbols (skip ::__doc__ projections).
    by_name: dict[str, str] = {}
    for s in store.list_symbols(scope):
        if s.kind.value in {"function", "method", "class"} and s.name not in by_name:
            by_name[s.name] = s.qualified_name
    resolved = []
    for item in gold:
        names = item.get("relevant_names") or item.get("relevant_qualified_names") or []
        qns = [by_name[n] for n in names if n in by_name]
        if qns:
            resolved.append({"query": item["query"], "relevant_qualified_names": qns})
    assert resolved, "gold symbols must resolve after ingest"

    ndcg = score_retrieval_ndcg(svc, scope, resolved, k=10, threshold=0.5)
    assert ndcg["mean_ndcg"] >= 0.5
    assert ndcg["passes_threshold"] is True

    community = score_community_vs_cochange(svc, scope, repo, min_support=2)
    assert "same_community_rate" in community
    assert community["label_source"] == "git_cochange"

    root = eval_artifact_root()
    assert (root / "cochange-explore-risk-latest.json").is_file()
    assert (root / "retrieval-ndcg-latest.json").is_file()
    assert (root / "community-vs-cochange-latest.json").is_file()
