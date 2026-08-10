"""Change-scoped review pack builder (RM-10 / RM-11 / RM-02 / RM-06)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .layered_ignore import collect_layered_ignore_rules, path_is_ignored
from .secret_scan import scan_text_for_secrets
from .tokens import estimate_tokens, tokens_from_chars


@dataclass
class ReviewPackResult:
    ok: bool
    files: list[dict[str, Any]] = field(default_factory=list)
    total_chars: int = 0
    estimated_tokens: int = 0
    secret_findings: list[dict[str, Any]] = field(default_factory=list)
    ignored_skipped: list[str] = field(default_factory=list)
    hotspots: list[dict[str, Any]] = field(default_factory=list)
    markdown: str = ""
    notes: list[str] = field(default_factory=list)
    over_token_budget: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "files": self.files,
            "total_chars": self.total_chars,
            "estimated_tokens": self.estimated_tokens,
            "secret_findings": self.secret_findings,
            "ignored_skipped": self.ignored_skipped,
            "hotspots": self.hotspots,
            "over_token_budget": self.over_token_budget,
            "notes": self.notes,
            "markdown": self.markdown,
        }


def git_changed_files(root: Path, *, staged: bool = False) -> list[str]:
    root = root.expanduser().resolve()
    args = ["git", "-C", str(root), "diff", "--name-only"]
    if staged:
        args.append("--cached")
    else:
        args.append("HEAD")
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return [ln.strip().replace("\\", "/") for ln in proc.stdout.splitlines() if ln.strip()]


def git_unified_diff(root: Path, rel: str, *, staged: bool = False) -> str:
    root = root.expanduser().resolve()
    args = ["git", "-C", str(root), "diff"]
    if staged:
        args.append("--cached")
    args.extend(["--", rel])
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""


def build_review_pack(
    root: Path,
    relative_paths: list[str],
    *,
    include_diff: bool = False,
    staged: bool = False,
    max_file_bytes: int = 200_000,
    token_budget: int | None = None,
    fail_on_secrets: bool = True,
    hotspot_min_tokens: int = 50,
) -> ReviewPackResult:
    root = root.expanduser().resolve()
    ignore_rules, ignore_sources = collect_layered_ignore_rules(root)
    notes = [f"layered_ignore:{s}" for s in ignore_sources]

    files_out: list[dict[str, Any]] = []
    secret_public: list[dict[str, Any]] = []
    ignored: list[str] = []
    parts: list[str] = [
        "# Astloom review pack",
        "",
        "Local change-scoped pack (optional export; graph tools remain primary).",
        "",
    ]
    total_chars = 0

    for raw in relative_paths:
        rel = str(raw or "").strip().replace("\\", "/").lstrip("./")
        if not rel:
            continue
        if path_is_ignored(rel, rules=ignore_rules):
            ignored.append(rel)
            continue
        path = root / rel
        if not path.is_file():
            notes.append(f"missing:{rel}")
            continue
        try:
            size = path.stat().st_size
        except OSError:
            notes.append(f"unreadable:{rel}")
            continue
        if size > max_file_bytes:
            notes.append(f"skipped_large:{rel}:{size}")
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            notes.append(f"unreadable:{rel}")
            continue

        for finding in scan_text_for_secrets(text):
            secret_public.append(
                {
                    "path": rel,
                    "rule_id": finding.rule_id,
                    "message": finding.message,
                    "line": finding.line,
                }
            )

        toks = estimate_tokens(text)
        total_chars += len(text)
        entry: dict[str, Any] = {
            "path": rel,
            "chars": len(text),
            "estimated_tokens": toks,
            "secret_hits": sum(1 for s in secret_public if s["path"] == rel),
        }
        diff = ""
        if include_diff:
            diff = git_unified_diff(root, rel, staged=staged)
            entry["diff_chars"] = len(diff)
            entry["diff_estimated_tokens"] = estimate_tokens(diff)
            total_chars += len(diff)
        files_out.append(entry)

        parts.append(f"## file: {rel}")
        parts.append("")
        parts.append(f"chars={len(text)} estimated_tokens={toks}")
        parts.append("")
        parts.append("```")
        parts.append(text)
        parts.append("```")
        parts.append("")
        if include_diff:
            parts.append(f"### diff: {rel}")
            parts.append("")
            parts.append("```diff")
            parts.append(diff or "(no diff)")
            parts.append("```")
            parts.append("")

    est = tokens_from_chars(total_chars)
    over = bool(token_budget is not None and est > int(token_budget))
    if over:
        notes.append(f"token_budget_exceeded:{est}>{token_budget}")

    ok = True
    if fail_on_secrets and secret_public:
        ok = False
        notes.append("secret_scan_failed")
    if over:
        ok = False

    body = "\n".join(parts)
    if secret_public:
        header = "# BLOCKED: secret findings\n\n" + "\n".join(
            f"- {s['path']}:{s['line']} {s['rule_id']}" for s in secret_public
        )
        markdown = header + "\n\n" + body
    else:
        markdown = body

    hotspots = sorted(
        (
            {
                "path": f["path"],
                "estimated_tokens": int(f["estimated_tokens"]),
                "chars": int(f["chars"]),
            }
            for f in files_out
            if int(f.get("estimated_tokens") or 0) >= int(hotspot_min_tokens)
        ),
        key=lambda row: row["estimated_tokens"],
        reverse=True,
    )

    return ReviewPackResult(
        ok=ok,
        files=files_out,
        total_chars=total_chars,
        estimated_tokens=est,
        secret_findings=secret_public,
        ignored_skipped=ignored,
        hotspots=hotspots,
        markdown=markdown,
        notes=notes,
        over_token_budget=over,
    )
