"""Unit tests for repo_pack (layered ignore, secrets, review pack, tokens)."""

from __future__ import annotations

from pathlib import Path

from repo_pack import (
    build_review_pack,
    collect_layered_ignore_globs,
    estimate_tokens,
    path_is_ignored,
    scan_text_for_secrets,
    tokens_from_chars,
)


def test_tokens_from_chars():
    assert tokens_from_chars(0) == 0
    assert tokens_from_chars(4) == 1
    assert estimate_tokens("abcd") == 1


def test_layered_ignore_gitignore_and_astloomignore(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("build/\n*.log\n", encoding="utf-8")
    (tmp_path / ".astloomignore").write_text("vendor/**\n", encoding="utf-8")
    globs, sources = collect_layered_ignore_globs(tmp_path)
    assert len(sources) == 2
    assert path_is_ignored("build/out.py", globs)
    assert path_is_ignored("app.log", globs)
    assert path_is_ignored("vendor/lib/x.py", globs)
    assert not path_is_ignored("src/main.py", globs)


def test_secret_scan_detects_pem_and_aws():
    text = "-----BEGIN PRIVATE KEY-----\nMIIE\n"
    hits = scan_text_for_secrets(text)
    assert any(h.rule_id == "private_key" for h in hits)
    hits2 = scan_text_for_secrets('key = "AKIAIOSFODNN7EXAMPLE"')
    assert any(h.rule_id == "aws_access_key" for h in hits2)


def test_review_pack_fail_closed_on_secrets(tmp_path: Path):
    (tmp_path / "ok.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("-----BEGIN RSA PRIVATE KEY-----\nx\n", encoding="utf-8")
    result = build_review_pack(tmp_path, ["ok.py", "bad.py"], fail_on_secrets=True)
    assert result.ok is False
    assert result.secret_findings
    assert result.estimated_tokens >= 0


def test_review_pack_token_budget(tmp_path: Path):
    (tmp_path / "big.py").write_text("x" * 400, encoding="utf-8")
    result = build_review_pack(tmp_path, ["big.py"], token_budget=10, fail_on_secrets=True)
    assert result.ok is False
    assert result.over_token_budget is True


def test_gitignore_negation_reincludes(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("*.log\n!keep.log\n", encoding="utf-8")
    from repo_pack import collect_layered_ignore_rules, path_is_ignored

    rules, _ = collect_layered_ignore_rules(tmp_path)
    assert path_is_ignored("drop.log", rules=rules)
    assert not path_is_ignored("keep.log", rules=rules)


def test_review_pack_hotspots(tmp_path: Path):
    (tmp_path / "small.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "big.py").write_text("x" * 800, encoding="utf-8")
    result = build_review_pack(
        tmp_path,
        ["small.py", "big.py"],
        fail_on_secrets=True,
        hotspot_min_tokens=50,
    )
    assert result.ok
    assert result.hotspots
    assert result.hotspots[0]["path"] == "big.py"


def test_review_pack_respects_astloomignore(tmp_path: Path):
    (tmp_path / ".astloomignore").write_text("secret.env\n", encoding="utf-8")
    (tmp_path / "secret.env").write_text("TOKEN=ghp_abcdefghijklmnopqrstuv\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")
    result = build_review_pack(tmp_path, ["secret.env", "app.py"], fail_on_secrets=True)
    assert "secret.env" in result.ignored_skipped
    assert result.ok is True
    assert [f["path"] for f in result.files] == ["app.py"]
